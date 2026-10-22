"""串口适配/应用故障注入；全部使用假驱动，不打开实际COM端口。"""
import ctypes as ct
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT / 'src/pc'))
from ecg_serial import WindowsSerial, SerialCapture, DCB, Timeouts, ComStat
from ecg_monitor_core import Monitor, Recorder, RecordingLimitError, demo_frames


HEADER = b'H,ECG-UART-1,test,s1,REPLAY,QRS-APPROX,360,-1,0xD\n'


class FakeReader:
    def __init__(self, *args, chunks=()):
        self.chunks = iter(chunks); self.closed = False

    def read(self, size):
        assert size == 4096 and not self.closed
        item = next(self.chunks, b'')
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True


class NativeTests(unittest.TestCase):
    def api(self):
        api = Mock()
        api.CreateFileW.return_value = 123
        for name in ('GetCommState', 'SetCommState', 'SetCommTimeouts', 'ClearCommError', 'ReadFile', 'CloseHandle'):
            getattr(api, name).return_value = 1
        return api

    def test_layout_and_explicit_configuration_no_flush_or_write(self):
        self.assertEqual((ct.sizeof(DCB), ct.sizeof(Timeouts), ct.sizeof(ComStat)), (28, 20, 12))
        api = self.api(); config = []; timeout = []
        api.SetCommState.side_effect = lambda handle, p: config.append((p._obj.baud, p._obj.flags, p._obj.byte_size, p._obj.parity, p._obj.stop_bits)) or 1
        api.SetCommTimeouts.side_effect = lambda handle, p: timeout.append(bytes(p._obj)) or 1
        reader = WindowsSerial('com14', api=api)
        self.assertEqual(api.CreateFileW.call_args.args, ('\\\\.\\COM14', 0xC0000000, 0, None, 3, 0, None))
        self.assertEqual(config, [(115200, 1, 8, 0, 0)])
        self.assertEqual(timeout[0], bytes(Timeouts(0xFFFFFFFF, 0, 0, 0, 0)))
        self.assertEqual(reader.read(), b'')
        api.ReadFile.assert_not_called()
        api.WriteFile.assert_not_called(); api.PurgeComm.assert_not_called()
        reader.close(); reader.close(); api.CloseHandle.assert_called_once_with(123)

    def test_bounded_binary_read_keeps_nul_and_high_bytes(self):
        api = self.api(); payload = b'\x00\xff\r\n'
        def status(handle, error, state):
            state._obj.input_bytes = 9000
            return 1
        def read(handle, buffer, size, count, overlapped):
            self.assertEqual(size, 4096)
            ct.memmove(buffer, payload, len(payload)); count._obj.value = len(payload)
            return 1
        api.ClearCommError.side_effect = status; api.ReadFile.side_effect = read
        reader = WindowsSerial('COM1', api=api)
        self.assertEqual(reader.read(), payload); reader.close()

    def test_open_config_and_read_failures_release_handle(self):
        api = self.api(); api.CreateFileW.return_value = ct.c_void_p(-1).value
        with self.assertRaises(OSError): WindowsSerial('COM14', api=api)
        api.CloseHandle.assert_not_called()
        for stage in ('GetCommState', 'SetCommState', 'SetCommTimeouts'):
            api = self.api(); getattr(api, stage).return_value = 0
            with self.assertRaises(OSError): WindowsSerial('COM14', api=api)
            api.CloseHandle.assert_called_once_with(123)
        api = self.api(); api.ClearCommError.return_value = 0
        reader = WindowsSerial('COM14', api=api)
        with self.assertRaises(OSError): reader.read()
        reader.close()

    def test_driver_error_not_reported_as_source_drop(self):
        api = self.api()
        def error(handle, bits, state):
            bits._obj.value = 1
            return 1
        api.ClearCommError.side_effect = error
        reader = WindowsSerial('COM14', api=api)
        with self.assertRaisesRegex(OSError, 'flags=0x1'): reader.read()
        api.ReadFile.assert_not_called(); reader.close()

    def test_read_failure_and_close_failure_are_observable(self):
        api = self.api()
        def status(handle, errors, state):
            state._obj.input_bytes = 12
            return 1
        api.ClearCommError.side_effect = status; api.ReadFile.return_value = 0
        reader = WindowsSerial('COM14', api=api)
        with self.assertRaises(OSError): reader.read()
        api.CloseHandle.return_value = 0
        with self.assertRaises(OSError): reader.close()
        with self.assertRaises(OSError): reader.read()
        reader.close(); api.CloseHandle.assert_called_once()

    def test_invalid_names_never_open_arbitrary_file(self):
        api = self.api()
        for name in ('COM0', 'COM01', 'COM14.txt', 'C:/file', '\\\\.\\COM14', '', None):
            with self.assertRaises(ValueError): WindowsSerial(name, api=api)
        with self.assertRaises(ValueError): WindowsSerial('COM14', baud=123, api=api)
        api.CreateFileW.assert_not_called()


class CaptureTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / 'tmp/pc_serial_tests'; parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_empty_reads_chunk_boundaries_and_replay_match(self):
        payload = HEADER + b'W,0,2,-1,NA,0,NA\r\nE,1,0,0,-1,?,-1\n'
        chunks = [b''] + [payload[i:i+3] for i in range(0, len(payload), 3)] + [b'']
        reader = FakeReader(chunks=chunks)
        m = Monitor(Recorder(self.path/'capture'))
        capture = SerialCapture(m, 'COM14', factory=lambda *args: reader)
        for _ in chunks: capture.poll()
        capture.close(); capture.close(); summary = m.finish('stopped_by_user')
        raw = (self.path/'capture/raw.log').read_bytes()
        replay = Monitor(); replay.feed(raw); replay.finish()
        self.assertEqual(raw, payload); self.assertEqual(m.counts, replay.counts)
        self.assertEqual(list(m.samples), list(replay.samples))
        self.assertEqual(list(m.events), list(replay.events))
        self.assertEqual(summary['input']['received_bytes'], len(payload))
        self.assertTrue(reader.closed and summary['input']['closed'])

    def test_no_header_is_raw_evidence_not_invented_waveform(self):
        m = Monitor(Recorder(self.path/'no_header'))
        reader = FakeReader(chunks=[b'Hello World\n', b'W,0,1,1,NA\n'])
        capture = SerialCapture(m, 'COM14', factory=lambda *args: reader)
        capture.poll(); capture.poll(); capture.close(); m.finish('stopped_by_user')
        self.assertEqual(m.counts['samples'], 0); self.assertIsNone(m.header)
        self.assertEqual((self.path/'no_header/raw.log').read_bytes(), b'Hello World\nW,0,1,1,NA\n')

    def test_open_failure_retains_attempted_configuration(self):
        m = Monitor(Recorder(self.path/'failed'))
        with self.assertRaises(OSError):
            SerialCapture(m, 'COM14', factory=Mock(side_effect=OSError('occupied')))
        m.finish('start_error')
        summary = json.loads((self.path/'failed/summary.json').read_text())
        self.assertEqual(summary['input']['port'], 'COM14')
        self.assertEqual(summary['input']['error'], 'occupied')
        self.assertFalse(summary['input']['opened'])
        self.assertTrue(summary['input']['closed'])

    def test_keyboard_interrupt_cli_closes_and_preserves_raw(self):
        import ecg_monitor
        from types import SimpleNamespace
        reader = FakeReader(chunks=[HEADER])
        args = SimpleNamespace(output_dir=self.path/'interrupted', max_bytes=65536,
                               serial='COM14', baud=115200, seconds=1)
        with patch.object(ecg_monitor, 'SerialCapture', side_effect=lambda m, p, b: SerialCapture(m, p, b, factory=lambda *args: reader)):
            with patch.object(ecg_monitor.time, 'sleep', side_effect=KeyboardInterrupt), patch('builtins.print'):
                code = ecg_monitor.headless(args)
        self.assertEqual(code, 130); self.assertTrue(reader.closed)
        self.assertEqual((self.path/'interrupted/raw.log').read_bytes(), HEADER)

    def test_disconnect_partial_frame_saved_and_not_joined_to_new_connection(self):
        for n, chunks in enumerate(([HEADER, b'W,0,1,', OSError('unplugged')], [b'7,NA\n'])):
            m = Monitor(Recorder(self.path/str(n))); reader = FakeReader(chunks=chunks)
            capture = SerialCapture(m, 'COM14', factory=lambda *args: reader)
            try:
                for _ in chunks: capture.poll()
            except OSError:
                self.assertEqual(m.input_info['error'], 'unplugged')
            capture.close(); summary = m.finish('input_error' if n == 0 else 'stopped_by_user')
            self.assertEqual(m.counts['samples'], 0)
            self.assertTrue(reader.closed)
            self.assertEqual(summary['protocol_counts'].get('truncated', 0), 1 if n == 0 else 0)

    def test_record_limit_closes_and_preserves_reason(self):
        m = Monitor(Recorder(self.path/'limit', 1024))
        reader = FakeReader(chunks=[frame for _, frame in demo_frames(3)])
        capture = SerialCapture(m, 'COM14', factory=lambda *args: reader)
        with self.assertRaises(RecordingLimitError):
            for _ in range(100): capture.poll()
        capture.close(); m.finish('recording_limit')
        result = json.loads((self.path/'limit/summary.json').read_text())
        self.assertTrue(reader.closed)
        self.assertIn('上限', result['input']['error'])
        self.assertEqual(result['reason'], 'recording_limit')

    def test_headless_uses_same_receiver_and_saves_close_on_error(self):
        import ecg_monitor
        from types import SimpleNamespace
        reader = FakeReader(chunks=[HEADER, b'W,0,1,2,NA\n', OSError('unplugged')])
        args = SimpleNamespace(output_dir=self.path/'cli', max_bytes=65536, serial='COM14', baud=115200, seconds=1)
        with patch.object(ecg_monitor, 'SerialCapture', side_effect=lambda m, p, b: SerialCapture(m, p, b, factory=lambda *args: reader)):
            with patch('builtins.print'):
                code = ecg_monitor.headless(args)
        self.assertEqual(code, 2); self.assertTrue(reader.closed)
        result = json.loads((self.path/'cli/summary.json').read_text())
        self.assertEqual(result['counts']['samples'], 1)
        self.assertIn('unplugged', result['reason'])

    def test_hidden_gui_connect_empty_read_stop_and_reconnect(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('没有Tkinter')
        import ui.monitor as ecg_monitor
        root = tk.Tk(); root.withdraw()
        readers = []
        def receiver(monitor, port):
            reader = FakeReader(chunks=[b'', HEADER + b'W,0,2,1,NA,2,NA\n'])
            readers.append(reader)
            return SerialCapture(monitor, port, factory=lambda *args: reader)
        try:
            with patch.object(ecg_monitor, 'new_directory', side_effect=[self.path/'ui1', self.path/'ui2']), \
                 patch.object(ecg_monitor, 'SerialCapture', side_effect=receiver), \
                 patch.object(ecg_monitor, 'enumerate_ports', return_value=([dict(port='COM14', label='fake', device_id='', candidate=True)], [])):
                app = ecg_monitor.Application(root)
                self.assertEqual(app.state, 'idle'); self.assertTrue(app.canvas.find_withtag('guide'))
                app.port_text.set('COM14')
                app.open_serial(); app.tick()
                # 空读：仍是等待态，不画波形，不显示上次单位；诊断详情写明尚无H。
                self.assertTrue(app.running); self.assertEqual(app.state, 'serial_wait')
                self.assertIn('尚未收到任何字节', app.wait_hint())
                self.assertIn('尚未收到合法H', '\n'.join(app.detail_lines()))
                self.assertFalse(app.canvas.find_withtag('wave')); self.assertEqual(app.card_vars['hr'].get(), '—')
                app.tick(); self.assertEqual(app.monitor.counts['samples'], 2)
                self.assertEqual(app.state, 'serial_live'); self.assertTrue(app.canvas.find_withtag('wave'))
                self.assertEqual(app.card_vars['cls'].get(), '未提供')  # caps无CLASS时不显示为正常
                app.stop(); self.assertTrue(readers[0].closed)
                self.assertEqual(app.state, 'stopped'); self.assertIn('历史', app.card_notes['samples'].get())
                app.open_serial(); self.assertEqual(app.monitor.counts['samples'], 0)
                self.assertEqual(app.state, 'serial_wait'); self.assertEqual(app.card_notes['samples'].get(), '')
                self.assertIn('尚未收到合法H', '\n'.join(app.detail_lines()))
                app.stop(); self.assertTrue(readers[1].closed)
        finally:
            root.destroy()

    def test_hidden_gui_header_without_waveform_and_error_state(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('没有Tkinter')
        import ui.monitor as ecg_monitor
        root = tk.Tk(); root.withdraw()
        reader = FakeReader(chunks=[b'Hello World\n', OSError('unplugged')])
        try:
            with patch.object(ecg_monitor, 'new_directory', side_effect=[self.path/'ui_err']), \
                 patch.object(ecg_monitor, 'SerialCapture', side_effect=lambda m, p: SerialCapture(m, p, factory=lambda *a: reader)), \
                 patch.object(ecg_monitor, 'enumerate_ports', return_value=([dict(port='COM14', label='fake', device_id='', candidate=True)], [])):
                app = ecg_monitor.Application(root); app.port_text.set('COM14')
                app.open_serial(); app.tick()
                # 收到非协议文本：说明已保存原文但仍在等H，不显示猜测波形。
                self.assertEqual(app.state, 'serial_wait'); self.assertIn('尚未收到合法H报文', app.wait_hint())
                self.assertFalse(app.canvas.find_withtag('wave'))
                app.tick()
                self.assertFalse(app.running); self.assertEqual(app.state, 'error'); self.assertTrue(reader.closed)
                self.assertIn('unplugged', app.message_text.get())
        finally:
            root.destroy()

    def test_hidden_gui_demo_and_replay_states_and_canvas_bounds(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('没有Tkinter')
        import ui.monitor as ecg_monitor
        root = tk.Tk(); root.withdraw()
        log = self.path/'replay.log'
        log.write_bytes(b''.join(frame for _, frame in demo_frames(2.01)))
        try:
            with patch.object(ecg_monitor, 'new_directory', side_effect=[self.path/'d1', self.path/'r1']):
                app = ecg_monitor.Application(root)
                app.start_demo(); self.assertEqual(app.state, 'demo')
                app.started -= 1.0; app.tick()
                self.assertGreater(app.monitor.counts['samples'], 0)
                self.assertIn('演示', app.table.heading('pos', 'text'))
                app.stop(); self.assertEqual(app.state, 'stopped')
                app.start('file', log); self.assertEqual(app.state, 'replay')
                for _ in range(50):
                    app.tick()
                    if not app.running: break
                self.assertEqual(app.state, 'stopped'); self.assertIn('全部处理完', app.message_text.get())
                # 隐藏窗口可能未映射，按draw实际采用的尺寸检查所有图元不越界。
                for size in ((300, 180), (760, 260), (1600, 700)):
                    app.canvas.configure(width=size[0], height=size[1]); root.update_idletasks(); app.draw()
                    bbox = app.canvas.bbox('all'); w, h = app.plot_size
                    self.assertTrue(app.canvas.find_withtag('wave'))
                    self.assertLessEqual(bbox[2], w + 2, size); self.assertLessEqual(bbox[3], h + 2, size)
                    self.assertGreaterEqual(min(bbox[0], bbox[1]), -2, size)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
