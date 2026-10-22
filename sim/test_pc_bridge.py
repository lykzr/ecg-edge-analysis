"""端口身份与GUI中转后台闭环；假双串口/实际PS C核心，不替代实物验收。"""
import csv
import json
from pathlib import Path
import queue
import struct
import sys
import time
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path[:0] = [str(ROOT/'src/pc'), str(ROOT/'sim')]
from ecg_ports import select_port, validate_port, remember_identity, remembered_identity
from ecg_bridge_worker import BridgeWorker
from ecg_capture_core import FIELDS
import test_ecg_bridge as host
Node = host.Node


def devices():
    return [dict(port='COM23', label='CH340', device_id='usb-board', candidate=True),
            dict(port='COM4', label='CH340', device_id='usb-radio', candidate=True)]


class PortTests(unittest.TestCase):
    def test_unique_candidate_and_ambiguity(self):
        self.assertEqual(select_port(devices()), '')
        self.assertEqual(select_port(devices()[:1]), 'COM23')
        self.assertEqual(select_port(devices(), excluded='COM23'), 'COM4')

    def test_identity_follows_com_and_never_falls_back_when_missing(self):
        previous = devices()[0]
        new = dict(previous, port='COM39')
        self.assertEqual(select_port([new, devices()[1]], previous), 'COM39')
        self.assertEqual(select_port(devices()[1:], previous), '')
        self.assertEqual(select_port([new], identity='usb-board'), 'COM39')
        self.assertEqual(select_port(devices(), identity='missing'), '')

    def test_reused_port_or_conflict_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_port('COM23', devices()[0], [dict(devices()[1], port='COM23')])
        with self.assertRaises(ValueError):
            validate_port('COM23', devices()[0], devices(), excluded='COM23')

    def test_memory_keeps_identity_not_port(self):
        path = ROOT/'tmp/pc_bridge_tests'/uuid.uuid4().hex/'devices.json'
        self.assertEqual(remembered_identity('zynq', path), '')
        remember_identity('zynq', devices()[0], path)
        self.assertEqual(json.loads(path.read_text()), {'zynq': 'usb-board'})
        self.assertEqual(remembered_identity('zynq', path), 'usb-board')


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        host.UsbBridgeTests.setUpClass()
        cls.lib = host.UsbBridgeTests.lib
        cls.directory = ROOT/'tmp/pc_bridge_tests'/uuid.uuid4().hex
        cls.directory.mkdir(parents=True)

    def source_csv(self, count=160):
        path = self.directory/(uuid.uuid4().hex+'.csv')
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f); w.writerow(FIELDS)
            for i in range(count):
                w.writerow([7+i/500, 8388608+i, 8388608+(20000*256 if i%100 == 40 else 0), 0, 0])
        return path

    def run_worker(self, kind='csv', **kwargs):
        node = Node(self.lib)
        source = kwargs.pop('source', None) or self.source_csv()
        w = BridgeWorker(kind, source, 'COM23', self.directory/uuid.uuid4().hex,
                         port_factory=lambda *args: node, realtime=False,
                         clock=lambda: node.now/1e6, pause=0, **kwargs)
        w.start(); w.join(20)
        if w.is_alive(): w.stop(); w.join(5)
        self.assertFalse(w.is_alive())
        self.assertTrue(node.closed)
        return w, node

    def test_csv_actual_ps_core_echo_and_exact_original(self):
        p = self.source_csv(); w, node = self.run_worker(source=p)
        info, capture, source, (result, events, header) = w.snapshot()
        self.assertIsNone(info['error'], info)
        self.assertEqual(info['reason'], 'completed'); self.assertTrue(info['done'])
        self.assertEqual((info['source_samples'], info['confirmed'], info['echoed']), (160,)*3)
        self.assertEqual(node.inputs, [20000 if i%100 == 40 else 0 for i in range(160)])
        self.assertEqual((w.directory/'capture/source.csv').read_bytes(), p.read_bytes())
        self.assertEqual(capture['csv_first_time_s'], 7)
        self.assertEqual(header.source, 'REPLAY'); self.assertIsNone(info['upstream_source_drop'])
        self.assertLessEqual(info['source_queue_peak'], 2048)
        self.assertTrue((w.directory/'results/raw.log').exists())
        self.assertEqual(json.loads((w.directory/'summary.json').read_text())['confirmed'], 160)

    def test_live_34byte_two_ports_and_finite_limit(self):
        payload = b'prefix'+b''.join(b'\xaa\xbb'+b''.join(struct.pack('>II', 8388608+j, 8388608+256*j) for j in range(i, i+4)) for i in range(0, 80, 4))
        class Source:
            def __init__(self): self.data = bytearray(payload); self.closed = False
            def read(self, size):
                b = bytes(self.data[:17]); del self.data[:17]; return b
            def close(self): self.closed = True
        source = Source()
        w, node = self.run_worker('serial', source='COM4', sample_limit=60,
                                  source_factory=lambda *args: source)
        info, cap, _, (_, _, header) = w.snapshot()
        self.assertIsNone(info['error'], info); self.assertTrue(info['done'])
        self.assertEqual(info['source_end'], 'sample_limit'); self.assertEqual(info['confirmed'], 60)
        self.assertEqual(node.inputs, list(range(60))); self.assertTrue(source.closed)
        self.assertEqual(header.source, 'ADC'); self.assertEqual(cap['initial_bytes_skipped'], 6)

    def test_bad_source_fails_without_completed_claim(self):
        p = self.source_csv(); p.write_text('invalid\n', encoding='utf-8')
        w, _ = self.run_worker(source=p)
        info = w.snapshot()[0]
        self.assertIsNotNone(info['error']); self.assertEqual(info['reason'], 'failed')
        self.assertFalse(info['done']); self.assertTrue((w.directory/'capture/source.csv').exists())

    def test_same_port_and_queue_overflow_fail_closed(self):
        with self.assertRaises(ValueError):
            BridgeWorker('serial', 'COM23', 'com23', self.directory/'unused')
        w = BridgeWorker('csv', 'unused', 'COM23', self.directory/'unused')
        for i in range(2048): w.enqueue(None, i)
        with self.assertRaises(BufferError): w.enqueue(None, 1)
        self.assertEqual(w.queue.qsize(), 2048)

    def test_stop_before_ready_closes_and_saves_partial(self):
        w = BridgeWorker('csv', 'unused', 'COM23', self.directory/uuid.uuid4().hex,
                         port_factory=lambda *args: Node(self.lib), pause=0)
        w.stop(); w.start(); w.join(5)
        info = w.snapshot()[0]
        self.assertFalse(w.is_alive()); self.assertEqual(info['reason'], 'stopped_by_user')
        self.assertFalse(info['done']); self.assertIsNone(info['error'])

    def test_no_response_times_out_preserves_upload(self):
        class Silent:
            closed = False
            def read(self, n): return b''
            def write(self, b): return len(b)
            def close(self): self.closed = True
        t = [0.0]; port = Silent()
        def clock(): t[0] += .05; return t[0]
        w = BridgeWorker('csv', 'unused', 'COM23', self.directory/uuid.uuid4().hex,
                         port_factory=lambda *args: port, clock=clock, pause=0)
        w.start(); w.join(5)
        info = w.snapshot()[0]
        self.assertFalse(w.is_alive()); self.assertIn('TimeoutError', info['error'])
        self.assertTrue(port.closed); self.assertFalse(info['done'])
        self.assertGreater((w.directory/'upload.log').stat().st_size, 0)

    def test_stop_during_source_drains_confirmed_partial_session(self):
        node = Node(self.lib)
        class FastPort:
            def read(self, n):
                for _ in range(128): node.tick()
                data = bytes(node.out[:n]); del node.out[:n]; return data
            def write(self, data): return node.write(data)
            def close(self): node.close()
        w = BridgeWorker('csv', self.source_csv(3000), 'COM23', self.directory/uuid.uuid4().hex,
                         port_factory=lambda *a: FastPort(), realtime=True, pause=.001)
        w.start()
        deadline = time.monotonic()+3
        while w.capture.snapshot()[0]['total'] < 20 and w.is_alive() and time.monotonic() < deadline:
            time.sleep(.005)
        w.stop(); w.join(5)
        info = w.snapshot()[0]
        self.assertFalse(w.is_alive()); self.assertIsNone(info['error'], info)
        self.assertTrue(info['done']); self.assertEqual(info['reason'], 'stopped_by_user')
        self.assertGreaterEqual(info['confirmed'], 20)
        self.assertLess(info['confirmed'], 3000); self.assertEqual(info['confirmed'], info['echoed'])
        self.assertEqual(w.capture.snapshot()[0]['total'], info['confirmed'])

    def test_record_limit_failure_closes_source_and_zynq(self):
        w, node = self.run_worker(maximum=4096)
        info = w.snapshot()[0]
        self.assertIsNotNone(info['error']); self.assertFalse(info['done'])
        self.assertFalse(w.capture.is_alive()); self.assertTrue(node.closed)
        self.assertTrue((w.directory/'summary.json').exists())

    def test_source_disconnect_closes_both_ports(self):
        class Source:
            closed = False
            def read(self, n): raise OSError('radio-unplugged')
            def close(self): self.closed = True
        source = Source()
        w, node = self.run_worker('serial', source='COM4', source_factory=lambda *a: source)
        info = w.snapshot()[0]
        self.assertIn('radio-unplugged', info['error'])
        self.assertFalse(info['done']); self.assertTrue(source.closed); self.assertTrue(node.closed)


class UiTests(unittest.TestCase):
    def test_hidden_window_ports_and_main_entry(self):
        import tkinter as tk
        from ui.bridge import BridgePanel
        from ui.monitor import Application
        root = tk.Tk(); root.withdraw()
        try:
            with patch('ui.bridge.enumerate_ports', return_value=(devices(), [])), \
                 patch('ui.bridge.remembered_identity', return_value='usb-board'):
                p = BridgePanel(root)
                root.update_idletasks()
                self.assertEqual(p.zynq.get(), 'COM23'); self.assertEqual(p.source.get(), 'COM4')
                p.tick(); p.window.destroy()
            with patch('ui.monitor.enumerate_ports', return_value=(devices(), [])), \
                 patch('ui.monitor.remembered_identity', return_value='usb-board'):
                app = Application(root)
                self.assertEqual(app.port_text.get(), 'COM23')
                self.assertEqual(app.bridge_button.cget('text'), '送样 / 双向中转…')
        finally:
            root.destroy()


if __name__ == '__main__': unittest.main()
