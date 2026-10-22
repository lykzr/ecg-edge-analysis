"""PC离线协议、序号/未知值、记录限额和CLI重放验证，不连接串口或运行模型。"""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT / 'src/pc'))
from ecg_uart import Decoder, Header, MASK
from ecg_monitor_core import Monitor, Recorder, RecordingLimitError, demo_frames
from ui.plot import plot_geometry, save_svg


def header(session='s1', fs=360, scale=-1, caps='0xD'):
    return f'H,ECG-UART-1,test,{session},REPLAY,QRS-APPROX,{fs},{scale},{caps}\n'.encode()


class ParserTests(unittest.TestCase):
    def test_chunked_crlf_partial_batch_matches_whole_stream(self):
        payload = header() + b'W,0,3,-32768,NA,-1,NA,32767,NA\r\nE,1,0,0,-1,?,-1\n'
        bulk, chunked = Monitor(), Monitor()
        bulk.feed(payload)
        for b in payload:
            chunked.feed(bytes([b]))
        self.assertEqual(list(bulk.samples), list(chunked.samples))
        self.assertEqual(list(bulk.events), list(chunked.events))
        self.assertEqual(bulk.decoder.counts, chunked.decoder.counts)
        self.assertEqual(chunked.counts['samples'], 3)
        self.assertEqual(chunked.visible_events()[0][1], 0)

    def test_max_line_overflow_nonascii_and_recovery(self):
        m = Monitor(); m.feed(header())
        m.feed(b'L,I,' + b'x' * 251 + b'\n')  # 恰好256字节含LF。
        m.feed(b'L,I,' + b'x' * 252 + b'\n')
        m.feed(b'L,I,\xff\nnoise from old firmware\nW,0,1,7,NA\n')
        self.assertEqual(m.decoder.counts['L'], 1)
        self.assertEqual(m.decoder.counts['overlong'], 1)
        self.assertEqual(m.decoder.counts['invalid'], 1)
        self.assertEqual(m.decoder.counts['unknown'], 1)
        self.assertEqual(m.counts['samples'], 1)
        self.assertLessEqual(len(m.decoder.buffer), 255)

    def test_missing_header_and_truncated_tail_are_not_valid_samples(self):
        m = Monitor(); m.feed(b'W,0,1,1,NA\n'); m.feed(header()); m.feed(b'W,0,1,2,NA')
        m.finish()
        self.assertEqual(m.decoder.counts['invalid'], 1)
        self.assertEqual(m.decoder.counts['truncated'], 1)
        self.assertEqual(m.counts['samples'], 0)

    def test_session_duplicate_metadata_and_reused_id(self):
        m = Monitor(); m.feed(header() + b'W,10,1,2,NA\n')
        m.feed(header()); self.assertEqual(len(m.samples), 1)
        m.feed(header(fs=500)); self.assertEqual(m.header.fs, 360)
        m.feed(header('s2', fs=-1)); self.assertFalse(m.samples)
        m.feed(header('s1')); self.assertEqual(m.header.session, 's2')
        self.assertEqual(m.counts['sessions'], 2)
        self.assertEqual(m.decoder.counts['invalid'], 2)

    def test_uint32_wave_wrap_gaps_and_out_of_order(self):
        m = Monitor(); m.feed(header())
        m.feed(f'W,{MASK-1},2,1,NA,2,NA\nW,0,1,3,NA\nW,3,2,4,NA,5,NA\n'.encode())
        before = list(m.samples); m.feed(b'W,3,1,4,NA\n')
        self.assertEqual(list(m.samples), before)
        self.assertEqual([p[1] for p in m.samples], [MASK-1, MASK, MASK+1, MASK+4, MASK+5])
        self.assertEqual(m.counts['wave_gap'], 2)
        self.assertEqual(m.decoder.counts['invalid'], 1)
        self.assertEqual(len(plot_geometry(m)['raw']), 2)

    def test_event_wrap_and_late_waveform_alignment(self):
        m = Monitor(); m.feed(header())
        m.feed(f'E,{MASK},0,0,-1,?,-1\nE,0,1,360,60.0,?,-1\n'.encode())
        self.assertFalse(m.visible_events())
        m.feed(b'W,0,2,1,NA,2,NA\n')
        self.assertEqual(len(m.visible_events()), 2)
        self.assertEqual(m.counts['event_gap'], 0)

    def test_first_seen_event_does_not_imply_missing_previous_recording(self):
        m = Monitor(); m.feed(header() + b'E,7,2,0,-1,?,-1\nE,9,362,360,60.0,?,-1\n')
        self.assertEqual(m.counts['event_gap'], 1)
        self.assertEqual(m.counts['events'], 2)

    def test_no_imagined_filter_or_classification_and_numeric_ranges(self):
        m = Monitor(); m.feed(header())
        m.feed(b'W,0,1,1,2\nW,0,1,32768,NA\nE,1,0,0,-1,N,90\nE,1,0,0,-1,?,90\n')
        m.feed(b'E,1,0,360,nan,?,-1\nW,0,1,-1,NA\n')
        self.assertEqual(m.decoder.counts['invalid'], 5)
        self.assertEqual(m.samples[-1][2:], (-1, None))

    def test_unknown_units_disable_time_and_voltage_and_split_drop_counts(self):
        m = Monitor(); m.feed(header(fs=-1) + b'W,0,1,4096,NA\nT,-1,-1,?,NA,-1,2,-1,7,1000\n')
        self.assertIsNone(m.header.scale); self.assertIsNone(m.header.fs)
        self.assertEqual(plot_geometry(m)['unit'], '码值（未标定）')
        self.assertEqual(m.status.event_drop, 2); self.assertEqual(m.status.tx_drop, 7)
        self.assertIsNone(m.status.source_drop)
        self.assertEqual(m.counts['wave_gap'], 0)

    def test_logs_with_commas_unknown_caps_and_unsupported_checksum(self):
        m = Monitor(); m.feed(header(caps='0x8D') + b'L,I,text,with,commas and spaces\n')
        self.assertEqual(m.logs[-1], 'I: text,with,commas and spaces')
        self.assertEqual(m.decoder.counts['unknown_caps'], 1)
        m.feed(header('bad', caps='0x4D')); self.assertEqual(m.header.session, 's1')
        self.assertEqual(m.decoder.counts['invalid'], 1)


class RecordingTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'tmp/pc_monitor_tests'; parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.path = Path(self.temp.name)
        self.path.resolve().relative_to(parent.resolve())

    def tearDown(self):
        self.temp.cleanup()

    def test_raw_bytes_csv_unknowns_and_non_overwrite(self):
        output = self.path / 'record'
        payload = header(fs=-1) + b'W,0,2,-1,NA,0,NA\r\n'
        m = Monitor(Recorder(output)); m.feed(payload); m.finish()
        self.assertEqual((output / 'raw.log').read_bytes(), payload)
        with (output / 'samples.csv').open(newline='', encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['raw'], '-1')
        for name in ('filt', 'time_s', 'raw_mv', 'filt_mv', 'scale', 'fs'):
            self.assertEqual(rows[0][name], '')
        with self.assertRaises(FileExistsError):
            Recorder(output)
        self.assertEqual((output / 'raw.log').read_bytes(), payload)

    def test_budget_stops_without_overwriting_and_saves_failure_reason(self):
        output = self.path / 'limited'; m = Monitor(Recorder(output, 1024))
        with self.assertRaises(RecordingLimitError):
            for _, frame in demo_frames(2): m.feed(frame)
        m.finish('recording_limit')
        result = json.loads((output / 'summary.json').read_text())
        self.assertEqual(result['reason'], 'recording_limit')
        self.assertLessEqual(sum(p.stat().st_size for p in output.iterdir() if p.name != 'summary.json'), 1024)
        self.assertTrue(all(f.closed for f in m.recorder.files.values()))

    def test_demo_partial_tail_and_svg_are_explicitly_synthetic(self):
        m = Monitor()
        for _, frame in demo_frames(2.01): m.feed(frame)
        self.assertEqual(m.counts['samples'], round(2.01 * 360))
        self.assertEqual(m.header.source, 'SYNTH'); self.assertEqual(m.header.detector, 'SYNTH-MARKERS')
        self.assertEqual(m.decoder.counts['invalid'], 0)
        self.assertTrue(all(p[3] is None for p in m.samples))
        self.assertIsNone(m.status.event_drop); self.assertIsNone(m.status.tx_drop)
        svg = self.path / 'wave.svg'; save_svg(m, svg)
        xml = ET.parse(svg).getroot(); self.assertEqual(len(xml.findall('{*}polyline')), 1)
        self.assertIn('未标定', svg.read_text(encoding='utf-8'))

    def test_cli_demo_replay_preserves_decoded_data(self):
        app = ROOT / 'src/pc/ecg_monitor.py'; one = self.path / 'one'; two = self.path / 'two'
        r = subprocess.run([sys.executable, '-B', str(app), '--headless', '--demo', '--seconds', '2.01', '--output-dir', str(one)], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, '-B', str(app), '--headless', '--replay', str(one/'raw.log'), '--output-dir', str(two)], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in ('raw.log', 'samples.csv', 'events.csv', 'status.csv', 'sessions.jsonl'):
            self.assertEqual((one/name).read_bytes(), (two/name).read_bytes(), name)
        self.assertEqual(json.loads((one/'summary.json').read_text())['counts']['samples'], 724)


if __name__ == '__main__':
    unittest.main()
