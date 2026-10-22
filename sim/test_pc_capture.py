"""厂商采集/CSV与GUI生命周期检查；真实串口和人工视觉验收另做。"""
import csv
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'src/pc'))
from ecg_capture_core import CaptureSample, CaptureWorker, VendorCsv, InitialFrames, FIELDS
from ui.capture import trace_geometry, CapturePanel
from ecg_ports import candidate_port


def frame(n=0):
    return b'\xaa\xbb' + b''.join(struct.pack('>II', 8388608+i+n, 8388608-i-n) for i in range(4))


class CaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = ROOT/'tmp/pc_capture_tests'/uuid.uuid4().hex[:12]
        cls.output.mkdir(parents=True)

    def destination(self, name):
        return self.output/(name+'_'+uuid.uuid4().hex[:6])

    def source(self, rows=80):
        path = self.destination('source').with_suffix('.csv')
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(FIELDS)
            for i in range(rows):
                writer.writerow([i/500, 8388608+i, 8388608-i*100, i*.25, -i*.75])
        return path

    def run_csv(self, source, **kwargs):
        w = CaptureWorker('csv', source, self.destination('csv_run'), realtime=False, **kwargs)
        w.start(); w.join(10); self.assertFalse(w.is_alive())
        return w

    def run_serial(self, chunks, **kwargs):
        class Fake:
            def __init__(self):
                self.chunks = iter(chunks); self.closed = False
            def read(self, size):
                assert size == 4096
                item = next(self.chunks, None)
                if item is None:
                    worker.stop(); return b''
                if isinstance(item, Exception): raise item
                return item
            def close(self): self.closed = True
        fake = Fake()
        worker = CaptureWorker('serial', 'COM123', self.destination('serial_run'),
                               serial_factory=lambda *args: fake, **kwargs)
        worker.start(); worker.join(10)
        self.assertFalse(worker.is_alive()); self.assertTrue(fake.closed)
        return worker

    def test_csv_preserves_source_and_both_channels(self):
        path = self.source(); w = self.run_csv(path)
        info, values = w.snapshot()
        self.assertIsNone(info['error']); self.assertTrue(info['csv_complete'])
        self.assertEqual(info['total'], 80)
        self.assertEqual((w.directory/'source.csv').read_bytes(), path.read_bytes())
        self.assertEqual(info['source_sha256_read'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(values[17].pair, (17, -1700))
        self.assertEqual(values[17].ecg_filtered, -12.75)
        with (w.directory/'normalized.csv').open() as stream:
            normalized = list(csv.DictReader(stream))
        self.assertEqual([int(r['sample']) for r in normalized], [(-i*100) >> 8 for i in range(80)])
        self.assertFalse((w.directory/'events.csv').exists())

    def test_wrong_schema_empty_or_bad_values_fail_and_keep_input(self):
        for text in ['timestamp(s),heart_rate(BPM)\n0,70\n', ','.join(FIELDS)+'\n',
                     ','.join(FIELDS)+'\n0,8388608,8388608,nan,0\n',
                     ','.join(FIELDS)+'\n0,16777216,8388608,0,0\n',
                     ','.join(FIELDS)+'\n0,8388608,8388608,0,0\n0.004,8388608,8388608,0,0\n',
                     ','.join(FIELDS)+'\n0,8388608.0,8388608,0,0\n']:
            p = self.destination('bad').with_suffix('.csv'); p.write_text(text, encoding='utf-8')
            w = self.run_csv(p)
            self.assertIsNotNone(w.snapshot()[0]['error'])
            self.assertTrue((w.directory/'source.csv').stat().st_size)
            self.assertTrue((w.directory/'summary.json').exists())

    def test_overlong_or_malformed_line_is_rejected(self):
        for line in ['x'*4097, '"unclosed']:
            p = self.destination('long').with_suffix('.csv')
            p.write_text(','.join(FIELDS)+'\n'+line+'\n', encoding='utf-8')
            self.assertIsNotNone(self.run_csv(p).snapshot()[0]['error'])

    def test_normalization_saturation_is_counted_not_applied_to_original(self):
        p = self.source(); w = self.run_csv(p, shift=0)
        self.assertIsNone(w.snapshot()[0]['error'])
        # 另测完整24位极值，不靠此样本范围推定全量程标定。
        p.write_text(','.join(FIELDS)+'\n0,0,16777215,0,0\n', encoding='utf-8')
        w = self.run_csv(p, shift=0)
        self.assertEqual(w.snapshot()[0]['clipped'], 1)
        self.assertEqual(w.snapshot()[1][0].ecg_raw, 16777215)
        self.assertIn('32767', (w.directory/'normalized.csv').read_text())

    def test_candidate_alignment_retains_prefix_and_no_false_source_drop(self):
        payload = b'\xffprefix'+b''.join(frame(i*4) for i in range(15))
        w = self.run_serial([payload[i:i+7] for i in range(0, len(payload), 7)])
        info, values = w.snapshot()
        self.assertIsNone(info['error']); self.assertEqual(info['total'], 60)
        self.assertEqual(info['initial_bytes_skipped'], 7)
        self.assertEqual(info['alignment'], 'candidate_3_frames_no_crc')
        self.assertIsNone(info['source_drop'])
        self.assertEqual(values[-1].pair, (59, -59))
        self.assertEqual((w.directory/'capture.bin').read_bytes(), payload)

    def test_locked_corruption_stops_no_resync(self):
        payload = frame()*3 + b'\xaa\xbb\x01'+bytes(31) + frame()*4
        w = self.run_serial([payload[:102], payload[102:]])
        self.assertIsNotNone(w.snapshot()[0]['error'])
        self.assertEqual(w.snapshot()[0]['total'], 12)
        self.assertEqual((w.directory/'capture.bin').read_bytes(), payload)

    def test_reject_10_byte_stream_and_preserve_truncated_tail(self):
        ten = b'\xaa\xbb'+struct.pack('>II', 8388608, 8388608)
        bad = self.run_serial([ten*300, ten*120])
        self.assertIsNotNone(bad.snapshot()[0]['error'])
        tail = self.run_serial([frame()*3 + b'\xaa\xbb\x00'])
        self.assertIsNone(tail.snapshot()[0]['error'])
        self.assertEqual(tail.snapshot()[0]['pending_bytes'], 3)
        self.assertFalse(tail.snapshot()[0]['csv_complete'])

    def test_driver_error_closes_and_retains_received_bytes(self):
        w = self.run_serial([frame()*3, OSError('unplug')])
        self.assertIn('unplug', w.snapshot()[0]['error'])
        self.assertEqual(w.snapshot()[0]['total'], 12)

    def test_budget_stop_and_nonoverwrite(self):
        w = self.run_csv(self.source(800), maximum=1024)
        self.assertIn('RecordingLimitError', w.snapshot()[0]['error'])
        self.assertLessEqual(json.loads((w.directory/'summary.json').read_text(encoding='utf-8'))['data_bytes'], 1024)
        summary = (w.directory/'summary.json').read_bytes()
        duplicate = CaptureWorker('csv', self.source(), w.directory, realtime=False)
        duplicate.start(); duplicate.join(10)
        self.assertIsNotNone(duplicate.snapshot()[0]['error'])
        self.assertEqual(summary, (w.directory/'summary.json').read_bytes())

    def test_display_is_bounded_but_records_are_full(self):
        w = self.run_csv(self.source(5003))
        info, values = w.snapshot()
        self.assertIsNone(info['error']); self.assertEqual(info['total'], 5003)
        self.assertEqual(len(values), 4096); self.assertEqual(values[0].index, 907)
        with (w.directory/'samples.csv').open() as stream:
            self.assertEqual(sum(1 for _ in stream), 5004)

    def test_port_candidates_are_not_fixed_and_ambiguity_is_not_guessed(self):
        self.assertEqual(candidate_port([{'port':'COM88','candidate':True}]), 'COM88')
        ports = [{'port':'COM88','candidate':True}, {'port':'COM9','candidate':True}]
        self.assertEqual(candidate_port(ports), '')
        self.assertEqual(candidate_port(ports, 'com88'), 'COM9')
        self.assertEqual(candidate_port([{'port':'COM4','candidate':False}]), '')

    def test_geometry_preserves_peak_and_unknown_filter(self):
        samples = tuple(CaptureSample(i, i/500, 8388608, 8388608+(1000 if i==243 else 0)) for i in range(500))
        for width,height in [(300,180), (760,260), (1600,700)]:
            points,b = trace_geometry(samples, 'ecg', False, width,height)
            self.assertTrue(all(b[4] <= x <= b[5] and b[6] <= y <= b[7] for x,y in points))
            self.assertAlmostEqual(min(y for _,y in points), b[7]-(1000-b[0])/(b[1]-b[0])*(b[7]-b[6]))
        self.assertEqual(trace_geometry(samples, 'ecg', True, 760,260), ([],None))

    def test_invalid_shift_and_source_rejected(self):
        for kind,shift in [('serial',-1), ('serial',24), ('other',8)]:
            with self.assertRaises(ValueError):
                CaptureWorker(kind,'COM1',self.destination('invalid'),shift=shift)

    def test_cancel_realtime_replay_closes_without_claiming_complete(self):
        worker = CaptureWorker('csv',self.source(5003),self.destination('cancel'),realtime=True)
        worker.start()
        import time
        deadline = time.monotonic()+3
        while worker.snapshot()[0]['total'] < 3 and worker.is_alive() and time.monotonic()<deadline:
            time.sleep(.005)
        worker.stop(); worker.join(3)
        self.assertFalse(worker.is_alive())
        info,_ = worker.snapshot()
        self.assertIsNone(info['error']); self.assertFalse(info['csv_complete'])
        self.assertLess(info['total'],5003)
        self.assertEqual(json.loads((worker.directory/'summary.json').read_text(encoding='utf-8'))['reason'],'stopped_by_user')

    def test_partial_initial_data_times_out_without_alignment_claim(self):
        ticks = iter([0., 10.])
        class Fake:
            def __init__(self): self.chunks=iter([b'\xaa',b''])
            def read(self, _): return next(self.chunks,b'')
            def close(self): pass
        worker=CaptureWorker('serial','COM4',self.destination('timeout'),serial_factory=lambda *args:Fake(),clock=lambda:next(ticks,10.))
        worker.start();worker.join(3)
        if worker.is_alive():worker.stop();worker.join(3)
        info,_=worker.snapshot()
        self.assertIn('TimeoutError',info['error']);self.assertEqual(info['alignment'],'not_locked')

    def test_cli_real_csv_entry(self):
        result = subprocess.run([sys.executable,'-B',str(ROOT/'src/pc/ecg_capture_core.py'),
                                 '--csv',str(self.source()),'--output-dir',str(self.destination('cli'))],
                                capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['total'],80)


class CaptureUiTests(unittest.TestCase):
    def test_hidden_panel_has_no_fake_board_metrics_and_closes(self):
        try:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
        except Exception as error:
            self.skipTest('Tk不可用：'+str(error))
        try:
            with patch('ui.capture.enumerate_ports', return_value=([],[])):
                panel = CapturePanel(root)
            panel.window.withdraw()
            self.assertIsNone(panel.worker)
            self.assertIn('不计算心率',panel.detail.get())
            panel.close(); panel.tick()
            self.assertFalse(panel.window.winfo_exists())
        finally:
            root.destroy()

    def test_main_entry_opens_capture_and_csv_runs_in_hidden_panel(self):
        try:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
        except Exception as error:
            self.skipTest('Tk不可用：'+str(error))
        try:
            from ui.monitor import Application
            app = Application(root)
            with patch('ui.capture.enumerate_ports', return_value=([], [])):
                app.open_capture()
            panel = app.capture_panel; panel.window.withdraw()
            self.assertEqual(str(app.serial_button.cget('state')), 'disabled')
            source = CaptureTests.output/'ui_source.csv'
            source.write_text(','.join(FIELDS)+'\n0,8388608,8388609,0,0.1\n0.002,8388607,8388610,0,0.2\n', encoding='utf-8')
            with patch('ui.capture.ROOT', CaptureTests.output):
                panel.start('csv', source)
            panel.worker.join(3); self.assertFalse(panel.worker.is_alive())
            panel.tick()
            self.assertIn('回放完成',panel.status.get())
            self.assertEqual(panel.worker.snapshot()[0]['total'],2)
            panel.close(); panel.tick()
            self.assertIsNone(app.capture_panel)
            self.assertEqual(str(app.serial_button.cget('state')), 'normal')
        finally:
            root.destroy()

    def test_refresh_follows_identity_not_old_com_number(self):
        try:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
        except Exception as error:
            self.skipTest('Tk不可用：'+str(error))
        try:
            old = dict(port='COM4',device_id='usb-instance-a',candidate=True,label='CH340')
            new = dict(old,port='COM28')
            other = dict(old,port='COM4',device_id='usb-instance-b')
            with patch('ui.capture.enumerate_ports',return_value=([old], [])):
                panel = CapturePanel(root)
            panel.window.withdraw(); self.assertEqual(panel.port.get(),'COM4')
            with patch('ui.capture.enumerate_ports',return_value=([new,other], [])):
                panel.refresh_ports()
            self.assertEqual(panel.port.get(),'COM28')
            panel.close(); panel.tick()
        finally:
            root.destroy()

    def test_changed_identity_is_rejected_before_open(self):
        try:
            import tkinter as tk
            root=tk.Tk();root.withdraw()
        except Exception as error:
            self.skipTest('Tk不可用：'+str(error))
        try:
            old=dict(port='COM4',device_id='usb-a',candidate=True,label='CH340')
            with patch('ui.capture.enumerate_ports',return_value=([old],[])):
                panel=CapturePanel(root)
            panel.window.withdraw()
            with patch('ui.capture.enumerate_ports',return_value=([dict(old,device_id='usb-b')],[])), patch.object(panel,'start') as start, patch('tkinter.messagebox.showerror') as error:
                panel.open_serial()
                start.assert_not_called();error.assert_called_once()
            panel.close();panel.tick()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
