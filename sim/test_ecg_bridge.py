"""实际PS C核心+电脑中转闭环；AXI为软件参考，串口为分块/限速假传输。"""
from collections import deque
import ctypes as ct
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/pc'), str(ROOT/'src/reference')]
from ecg_bridge_core import BridgeClient
from ecg_bridge_protocol import encode, decode, ack, samples
from ecg_bridge_capture import VendorFrames, InputConverter
from ecg_monitor_core import Monitor
from ecg_reference import Detector, Config

READ = ct.CFUNCTYPE(ct.c_uint32, ct.c_void_p, ct.c_uint32)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint32, ct.c_uint32)
READY = ct.CFUNCTYPE(ct.c_int, ct.c_void_p)
BYTE = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_ubyte)


class Io(ct.Structure):
    _fields_ = [('ctx', ct.c_void_p), ('read', READ), ('write', WRITE), ('ready', READY), ('byte', BYTE)]


class Node:
    def __init__(self, lib, rate=500, dirty=False, tx_stall=False, write_limit=7):
        self.lib, self.rate, self.dirty, self.tx_stall = lib, rate, dirty, tx_stall
        self.write_limit = write_limit
        self.now = self.next_tx = self.next_rx = 0
        self.rx, self.out, self.events = deque(), bytearray(), deque()
        self.inputs, self.output, self.upload = [], bytearray(), bytearray()
        self.finished = False
        self.callback_error = None
        self.detector = Detector(Config(sample_rate_hz=500))
        self.total = self.mask = self.pops = 0
        self.callbacks = (READ(self.safe(self.read_reg, 0)), WRITE(self.safe(self.write_reg, None)),
                          READY(self.safe(self.ready, 0)), BYTE(self.safe(self.byte, None)))
        self.io = Io(None, *self.callbacks)
        self.storage = ct.create_string_buffer(lib.ecg_bridge_size())
        lib.ecg_bridge_init(self.storage, self.io)

    def safe(self, callback, default):
        def wrapped(*args):
            try:
                return callback(*args)
            except BaseException as error:
                self.callback_error = error
                return default
        return wrapped

    def read_reg(self, _, offset):
        if offset == 0x24: return self.rate
        if offset == 0x28: return 120
        if offset == 0x2c: return 200
        if offset == 0x14: return self.detector.adaptive_threshold
        if offset == 0x10: return self.detector.integrated_energy
        if offset == 0x30: return self.total + (1 if self.dirty else 0)
        if offset == 0x1c: return len(self.events)
        if offset == 4: return bool(self.events)
        if offset in (8, 12, 24) and self.events:
            self.mask |= {8: 1, 12: 2, 24: 4}[offset]
            return self.events[0][{8: 0, 12: 1, 24: 2}[offset]]
        return 0

    def write_reg(self, _, offset, value):
        if offset == 4:
            # 不在ctypes回调内抛异常；留给测试外层检查。
            if not self.events or self.mask != 7:
                self.pops = -100000
            else:
                self.events.popleft(); self.pops += 1; self.mask = 0
            return
        self.inputs.append(ct.c_int16(value).value)
        state = self.detector.tick(self.inputs[-1])
        if state.qrs_valid:
            self.total += 1
            self.events.append((state.qrs_sample_index, state.rr_interval_samples, self.total))

    def ready(self, _):
        return not self.tx_stall and self.now >= self.next_tx

    def byte(self, _, value):
        self.out.append(value); self.output.append(value); self.next_tx = self.now + 87

    def tick(self, delta=100):
        self.now += delta
        if not self.finished:
            if self.rx and self.now >= self.next_rx:
                self.lib.ecg_bridge_feed(self.storage, self.rx.popleft(), self.now)
                self.next_rx = self.now + 87
            self.finished = bool(self.lib.ecg_bridge_step(self.storage, self.now))
        if self.callback_error:
            raise RuntimeError('假外设回调失败，禁止当作通过') from self.callback_error

    def read(self, limit):
        self.tick()
        n = min(limit, 13, len(self.out))
        data = bytes(self.out[:n]); del self.out[:n]; return data

    def write(self, data):
        n = min(self.write_limit, len(data))
        self.rx.extend(data[:n]); self.upload.extend(data[:n]); return n

    def field(self, n):
        return self.lib.ecg_bridge_field(self.storage, n)

    def error(self):
        return self.lib.ecg_bridge_error(self.storage).decode()

    def close(self):
        self.closed = True


class UsbBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gcc = os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
        if not gcc: raise RuntimeError('需要已有GCC；不自动安装，也不跳过主要闭环')
        cls.output = ROOT/'tmp/usb_bridge_tests'/uuid.uuid4().hex[:12]
        cls.output.mkdir(parents=True, exist_ok=False)
        binary = cls.output/('bridge.dll' if os.name == 'nt' else 'bridge.so')
        pic = ['-fPIC'] if os.name != 'nt' else []
        result = subprocess.run([gcc, '-shared', *pic, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
            '-I', str(ROOT/'src/ps/ecg_bridge'), str(ROOT/'src/ps/ecg_bridge/bridge.c'),
            str(ROOT/'sim/ecg_bridge_host.c'), '-o', str(binary)], capture_output=True,
            env=dict(os.environ, TMP=str(cls.output), TEMP=str(cls.output)), timeout=60)
        (cls.output/'compile.log').write_bytes(result.stdout+result.stderr)
        if result.returncode: raise RuntimeError(result.stderr.decode(errors='replace'))
        cls.lib = ct.CDLL(str(binary))
        cls.lib.ecg_bridge_size.restype = ct.c_size_t
        cls.lib.ecg_bridge_init.argtypes = [ct.c_void_p, Io]
        cls.lib.ecg_bridge_feed.argtypes = [ct.c_void_p, ct.c_ubyte, ct.c_uint64]
        cls.lib.ecg_bridge_step.argtypes = [ct.c_void_p, ct.c_uint64]
        cls.lib.ecg_bridge_field.argtypes = [ct.c_void_p, ct.c_uint]
        cls.lib.ecg_bridge_field.restype = ct.c_uint32
        cls.lib.ecg_bridge_error.argtypes = [ct.c_void_p]
        cls.lib.ecg_bridge_error.restype = ct.c_char_p
        cls.lib.ecg_bridge_test_time.argtypes = [ct.c_uint64]
        cls.lib.ecg_bridge_test_time.restype = ct.c_uint64

    def test_real_bsp_frequency_macro_and_two_second_boundary(self):
        freq = 666666687 // 2
        # 原表达式在CPU_FREQ边界余数归零；修复版须仍单调并给出正确微秒。
        ticks = [0, 1, freq-1, freq, 2*freq-1, 2*freq, 666666687,
                 2*freq+2, 4*freq, 60*freq, 3600*freq, 86400*freq]
        actual = [self.lib.ecg_bridge_test_time(t) for t in ticks]
        self.assertEqual(actual, [t*1000000//freq for t in ticks])
        self.assertEqual(actual, sorted(actual))
        self.assertEqual(self.lib.ecg_bridge_test_time(2*freq), 2000000)

    def run_values(self, values, name='case'):
        node = Node(self.lib); monitor = Monitor()
        client = BridgeClient(node, monitor, 'offline', 'SYNTH', clock=lambda: node.now/1e6)
        index = 0
        for _ in range(300000):
            if not client.eof and len(client.queue) < 256:
                batch = values[index:index+32]; client.add(batch); index += len(batch)
                if index == len(values): client.finish_source()
            client.pump()
            if client.done: break
        self.assertTrue(client.done, node.error())
        self.assertEqual(node.inputs, values)
        self.assertEqual(client.confirmed, len(values))
        self.assertEqual(monitor.counts['samples'], len(values))
        self.assertEqual(monitor.counts['wave_gap'], 0)
        self.assertEqual(monitor.counts['event_gap'], 0)
        self.assertEqual(monitor.decoder.counts['invalid'], 0)
        self.assertEqual(node.pops, len(monitor.events))
        self.assertLessEqual(node.field(3), 8192)
        (self.output/(name+'_upload.log')).write_bytes(node.upload)
        (self.output/(name+'_usb_rx.log')).write_bytes(node.output)
        return node, monitor, client

    def test_5003_samples_actual_c_bidirectional_and_reference_events(self):
        values = [(-20000 if ((i-100)//500)%2 else 20000) if i>=100 and (i-100)%500==0 else 0 for i in range(5003)]
        _, monitor, client = self.run_values(values, 'pulse5003')
        self.assertEqual([e.pos for e in monitor.events], [70+500*i for i in range(10)])
        self.assertEqual([e.rr for e in monitor.events], [0]+[500]*9)
        self.assertEqual([e.hr for e in monitor.events][1:], [60.0]*9)
        self.assertIsNone(monitor.status.source_drop)
        self.assertEqual(client.echoed, 5003)

    def test_empty_partial_and_signed_boundaries(self):
        for n in (0, 1, 3, 31, 32, 33, 65):
            with self.subTest(n=n):
                self.run_values(([0, -32768, 32767]*22)[:n], f'boundary{n}')

    def send_raw(self, packets, *, node=None, ticks=30000):
        node = node or Node(self.lib)
        node.rx.extend(b''.join(packets))
        for _ in range(ticks):
            node.tick()
            if node.finished: break
        return node

    def test_crc_error_before_any_sample_and_wrong_direction(self):
        init = encode('I,ECG-IN-1,test,500,REPLAY,-1')
        bad = bytearray(samples(0, [123])); bad[bad.index(b'*')+1] ^= 1
        node = self.send_raw([init, bad])
        self.assertEqual(node.error(), 'BAD_CRC'); self.assertEqual(node.inputs, [])
        for packet in (b'\xaa\xbb'+bytes(8), b'H,ECG-UART-1,wrong\n'):
            node = self.send_raw([packet]); self.assertTrue(node.field(1)); self.assertEqual(node.inputs, [])

    def test_config_and_freshness_reject(self):
        for node, error in [(Node(self.lib, rate=360), 'CONFIG_MISMATCH'), (Node(self.lib, dirty=True), 'NEED_FRESH_PL')]:
            self.send_raw([encode('I,ECG-IN-1,test,500,REPLAY,-1')], node=node)
            self.assertEqual(node.error(), error); self.assertEqual(node.inputs, [])

    def test_gap_duplicate_bad_value_and_end_total_reject(self):
        init = encode('I,ECG-IN-1,test,500,REPLAY,-1')
        for body, error in [('D,1,1,42', 'BAD_SEQUENCE'), ('D,0,1,32768', 'BAD_SAMPLE'),
                            ('F,1', 'BAD_TOTAL'), ('I,ECG-IN-1,new,500,REPLAY,-1', 'BAD_INIT')]:
            node = self.send_raw([init, encode(body)])
            self.assertEqual(node.error(), error); self.assertEqual(node.inputs, [])
        node = self.send_raw([init], ticks=1000)
        node.rx.extend(samples(0, [123]))
        for _ in range(2000): node.tick()
        node.rx.extend(samples(0, [123]))
        for _ in range(3000): node.tick()
        self.assertEqual(node.error(), 'BAD_SEQUENCE'); self.assertEqual(node.inputs, [123])

    def test_timeouts_stall_and_bounded_lines(self):
        node = self.send_raw([b'I,ECG-IN-1'], ticks=23000)
        self.assertEqual(node.error(), 'PARTIAL_TIMEOUT')
        node = self.send_raw([encode('I,ECG-IN-1,test,500,REPLAY,-1')], ticks=60000)
        self.assertEqual(node.error(), 'INPUT_TIMEOUT')
        node = self.send_raw([encode('I,ECG-IN-1,test,500,REPLAY,-1')], node=Node(self.lib, tx_stall=True))
        self.assertEqual(node.error(), 'UART_STALLED')
        node = self.send_raw([b'x'*256+b'\n'])
        self.assertEqual(node.error(), 'LINE_TOO_LONG')

    def test_client_queue_and_zero_write_timeout(self):
        node = Node(self.lib, write_limit=0)
        client = BridgeClient(node, Monitor(), 's', 'REPLAY', clock=lambda: node.now/1e6, capacity=32)
        client.add([0]*32)
        with self.assertRaises(BufferError): client.add([1])
        with self.assertRaises(TimeoutError):
            for _ in range(25000): client.pump()
        self.assertEqual(node.inputs, [])

    def test_cli_vendor_file_preserves_raw_and_records_actual_c_results(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        import ecg_bridge
        values = [20000 if i>=100 and (i-100)%500==0 else 0 for i in range(1004)]
        raw = b''
        for offset in range(0, len(values), 4):
            raw += b'\xaa\xbb'+b''.join((value*256+8388608).to_bytes(4,'big') +
                                      (-value*256+8388608).to_bytes(4,'big') for value in values[offset:offset+4])
        original = self.output/'vendor34.bin'; original.write_bytes(raw)
        output = self.output/'cli_vendor'
        node = Node(self.lib)
        args = ['ecg_bridge.py','--vendor-log',str(original),'--format','document_34',
                '--channel','1','--shift','8','--aligned','--samples','1003',
                '--source','SYNTH','--rate','500','--zynq-port','COM14','--output-dir',str(output)]
        factory = lambda *a, **kw: BridgeClient(*a, clock=lambda: node.now/1e6, **kw)
        with patch.object(sys,'argv',args), patch.object(ecg_bridge,'DuplexSerial',return_value=node), \
             patch.object(ecg_bridge,'BridgeClient',side_effect=factory), \
             patch.object(ecg_bridge.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ecg_bridge.main(), 0)
        summary = json.loads((output/'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['confirmed'], 1003)
        self.assertEqual(summary['observed_points'], 1004)
        self.assertEqual(summary['clipped'], 0)
        self.assertFalse(summary['board_validated'])
        self.assertEqual(node.inputs, values[:1003])
        self.assertEqual((output/'capture.bin').read_bytes(), raw)
        self.assertIn(b'A,ECG-IN-1,', (output/'controls.log').read_bytes())
        self.assertNotIn(b'A,ECG-IN-1,', (output/'results/raw.log').read_bytes())
        self.assertEqual((output/'usb_rx.log').read_bytes(), node.output)
        self.assertTrue(node.closed)

    def test_callback_error_fails_immediately(self):
        node = Node(self.lib)
        def broken(*args): raise RuntimeError('intentional callback failure')
        node.detector.tick = broken
        with self.assertRaisesRegex(RuntimeError, '回调失败'):
            self.send_raw([encode('I,ECG-IN-1,s,500,REPLAY,-1'), samples(0,[1])], node=node)

    def test_live_capture_bursts_continue_during_ack_wait(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        import ecg_bridge
        node=Node(self.lib)
        values=[32767 if i%2 else -32768 for i in range(5003)]
        class Capture:
            def __init__(self): self.index=0;self.closed=False;self.raw=bytearray()
            def read(self,size):
                # 每8ms才交付4点，区分源500Hz与蓝牙分包到达。
                due=min(len(values),(node.now//8000)*4)
                data=b''.join(b'\xaa\xbb'+(v*256+8388608).to_bytes(4,'big')+
                              (8388608).to_bytes(4,'big') for v in values[self.index:due])
                self.index=due;self.raw.extend(data);return data
            def close(self):self.closed=True
        capture=Capture();output=self.output/'live_burst'
        args=['ecg_bridge.py','--vendor-port','COM20','--format','source_10','--channel','1',
              '--shift','8','--aligned','--samples','5003','--source','ADC','--rate','500','--zynq-port','COM14',
              '--output-dir',str(output)]
        factory=lambda *a,**kw:BridgeClient(*a,clock=lambda:node.now/1e6,**kw)
        with patch.object(sys,'argv',args),patch.object(ecg_bridge,'DuplexSerial',return_value=node), \
             patch.object(ecg_bridge,'WindowsSerial',return_value=capture), \
             patch.object(ecg_bridge,'BridgeClient',side_effect=factory), \
             patch.object(ecg_bridge.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ecg_bridge.main(),0)
        summary=json.loads((output/'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(node.inputs,values)
        self.assertEqual(summary['confirmed'],5003)
        self.assertEqual((output/'capture.bin').read_bytes(),capture.raw)
        self.assertEqual(summary['clipped'],0)
        self.assertLessEqual(summary['queue_peak'],4096)
        self.assertTrue(capture.closed)

    def test_client_rejects_wrong_ack_session_and_crc(self):
        class Transport:
            def __init__(self): self.rx=b''
            def read(self, size): data,self.rx=self.rx,b''; return data
            def write(self, data): return len(data)
        for response in (encode('A,ECG-IN-1,other,0,READY,NA'), b'A,ECG-IN-1,s,0,READY,NA*00000000\n'):
            transport=Transport(); client=BridgeClient(transport,Monitor(),'s','REPLAY')
            client.pump(); transport.rx=response
            with self.assertRaises(ValueError): client.pump()

    def test_start_after_idle_does_not_false_uart_stall(self):
        node=Node(self.lib);node.now=10000000
        node=self.send_raw([encode('I,ECG-IN-1,s,500,REPLAY,-1')],node=node,ticks=1000)
        self.assertEqual(node.error(), '')
        self.assertIn(b',READY,NA*',node.output)

    def test_reversed_clock_preserves_failure_reason(self):
        node=Node(self.lib);node.tick(100)
        self.assertEqual(self.lib.ecg_bridge_step(node.storage, 99), 1)
        self.assertEqual(node.error(), 'CLOCK_REVERSED')

    def test_cli_bad_csv_rate_and_record_limit_are_failures(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        import ecg_bridge
        for name,content,limit in [('bad_rate','index,fs,sample\n0,360,1\n',65536),
                                   ('limit','sample\n'+'12345\n'*500,1024)]:
            original=self.output/(name+'.csv');original.write_text(content,encoding='utf-8')
            output=self.output/name;node=Node(self.lib)
            args=['ecg_bridge.py','--csv',str(original),'--rate','500','--source','REPLAY',
                  '--zynq-port','COM14','--output-dir',str(output),'--max-bytes',str(limit)]
            with patch.object(sys,'argv',args),patch.object(ecg_bridge,'DuplexSerial',return_value=node), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ecg_bridge.main(),1)
            summary=json.loads((output/'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['reason'],'failed');self.assertEqual(node.inputs,[])


class CaptureTests(unittest.TestCase):
    def test_native_partial_write_timeout_and_failure(self):
        from unittest.mock import Mock
        from ecg_bridge_serial import DuplexSerial
        api=Mock();api.CreateFileW.return_value=123
        for name in ('GetCommState','SetCommState','SetCommTimeouts','CloseHandle'):
            getattr(api,name).return_value=1
        captured=[]
        def write(handle,buffer,size,count,overlapped):
            captured.append(ct.string_at(buffer,size));count._obj.value=2;return 1
        api.WriteFile.side_effect=write
        port=DuplexSerial('COM14',api=api)
        self.assertEqual(port.write(b'abc'),2);self.assertEqual(captured,[b'abc'])
        api.WriteFile.side_effect=None;api.WriteFile.return_value=0
        with self.assertRaises(OSError): port.write(b'ab')
        port.close();api.CloseHandle.assert_called_once_with(123)
    def test_vendor_both_versions_every_split_and_conversion(self):
        for format, points in [('source_10', 1), ('document_34', 4)]:
            frame = b'\xaa\xbb'+bytes.fromhex('00000000 00ffffff')*points
            for split in range(len(frame)+1):
                decoder = VendorFrames(format)
                values = decoder.feed(frame[:split])+decoder.feed(frame[split:]); decoder.finish()
                self.assertEqual(values, [(-8388608, 8388607)]*points)
        converter = InputConverter(1, 8)
        self.assertEqual(converter.convert((-8388608,0)), -32768)
        self.assertEqual(converter.convert((-1,0)), -1)
        converter = InputConverter(2, 0)
        self.assertEqual(converter.convert((0,8388607)), 32767); self.assertEqual(converter.clipped, 1)

    def test_capture_does_not_guess_boundary_or_pad_tail(self):
        with self.assertRaises(ValueError): VendorFrames('auto')
        decoder = VendorFrames('source_10'); decoder.feed(b'\xaa')
        with self.assertRaises(ValueError): decoder.finish()
        with self.assertRaises(ValueError): VendorFrames('source_10').feed(b'\0'*10)

    def test_input_crc_known_vector_and_direction(self):
        import binascii
        self.assertEqual(binascii.crc32(b'123456789'), 0xCBF43926)
        self.assertEqual(decode(encode('D,0,1,-32768')), ['D','0','1','-32768'])
        self.assertEqual(ack(encode('A,ECG-IN-1,s,0,READY,NA')), ('s',0,'READY','NA'))
        with self.assertRaises(ValueError): ack(encode('D,0,1,1'))
        with self.assertRaises(ValueError): samples(0,[32768])


if __name__ == '__main__':
    unittest.main()
