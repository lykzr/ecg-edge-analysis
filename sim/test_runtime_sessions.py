"""真实360/500Hz C链路跨会话重置回归；串口为宿主模拟，不代替实板。"""
import ctypes as ct
import csv
import sys
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/pc'), str(ROOT/'sim')]
from ecg_bridge_core import BridgeClient
from ecg_bridge_protocol import encode
from ecg_monitor_core import Monitor
import test_runtime_link as link_tests
import test_pipeline500 as pipeline_tests


class ReusableNode(link_tests.Node):
    """镜像main.c在DONE物理发送后重置的路径；模拟UART总能即时发出。"""
    def __init__(self, lib):
        super().__init__(lib)
        self.rearmed = 0

    def tick(self):
        self.now += 100
        result = self.lib.ecg_link_step(self.state, self.now)
        if result and not self.lib.ecg_link_failed(self.state):
            if self.lib.ecg_link_rearm(self.state, self.now):
                raise AssertionError('正常结束后不能重置')
            self.rearmed += 1
        return result


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        link_tests.LinkTests.setUpClass()
        pipeline_tests.PipelineTests.setUpClass()
        cls.libs = {360: link_tests.LinkTests.lib, 500: pipeline_tests.PipelineTests.lib}
        for lib in cls.libs.values():
            lib.ecg_link_rearm.argtypes = [ct.c_void_p, ct.c_uint64]
            lib.ecg_link_rearm.restype = ct.c_int
            lib.ecg_link_failed.argtypes = [ct.c_void_p]
            lib.ecg_link_failed.restype = ct.c_uint

    def transfer(self, node, rate, values, session):
        monitor = Monitor()
        client = BridgeClient(node, monitor, session, 'REPLAY', profile='runtime'+str(rate),
                              clock=lambda: node.now/1e6, timeout=10)
        client.add(values)
        client.finish_source()
        for _ in range(300000):
            client.pump()
            if client.done:
                break
        self.assertTrue(client.done)
        self.assertEqual((client.confirmed, client.echoed), (len(values), len(values)))
        self.assertEqual(monitor.decoder.counts['invalid'], 0)
        self.assertFalse(client.lines, 'DONE后不能混入下一轮半行')
        return monitor

    def test_consecutive_sessions_reset_beats_rr_samples_and_waveforms(self):
        for rate, lib in self.libs.items():
            with self.subTest(rate=rate):
                node = ReusableNode(lib)
                values = [18000 if i % rate == rate//2 else 0 for i in range(3000)]
                first = self.transfer(node, rate, values, 'first')
                second = self.transfer(node, rate, values, 'second')
                self.assertEqual(node.rearmed, 2)
                self.assertEqual([(s[0], s[2]) for s in first.samples], [(s[0], s[2]) for s in second.samples])
                self.assertGreater(len(first.events), 2)
                self.assertEqual([(e.seq,e.pos,e.rr) for e in first.events],
                                 [(e.seq,e.pos,e.rr) for e in second.events])
                self.assertEqual(second.events[0].rr, 0)
                self.assertEqual(second.events[0].seq, 1)
                self.assertEqual(second.header.session, 'second')

    def test_short_or_zero_session_then_longer_session(self):
        for rate, lib in self.libs.items():
            with self.subTest(rate=rate):
                node = ReusableNode(lib)
                for index, count in enumerate((0, 17, 1000)):
                    monitor = self.transfer(node, rate, [0]*count, 'stop_'+str(index))
                    self.assertEqual(monitor.counts['samples'], count)
                    self.assertFalse(monitor.events)
                self.assertEqual(node.rearmed, 3)

    def test_idle_wait_does_not_end_application_and_new_session_works(self):
        for rate, lib in self.libs.items():
            with self.subTest(rate=rate):
                node = ReusableNode(lib)
                self.transfer(node, rate, [0]*100, 'before_idle')
                # 关闭的消费者不缓存线上的周期H；设备仍以真实单调时间推进。
                for _ in range(120):
                    node.now += 1000000
                    for _ in range(5):
                        node.tick()
                    node.rx.clear()
                self.assertFalse(lib.ecg_link_failed(node.state))
                self.transfer(node, rate, [1]*100, 'after_idle')
                self.assertEqual(node.rearmed, 2)

    def test_rearm_forbidden_during_active_or_faulted_session(self):
        for rate, lib in self.libs.items():
            with self.subTest(rate=rate):
                node = link_tests.Node(lib)
                self.assertEqual(lib.ecg_link_rearm(node.state, 0), -1)
                for byte in encode(f'I,ECG-IN-1,broken,{rate},REPLAY,4096'):
                    lib.ecg_link_feed(node.state, byte, node.now)
                self.assertEqual(lib.ecg_link_rearm(node.state, 0), -1)
                for byte in b'D,0,1,0*00000000\n':
                    lib.ecg_link_feed(node.state, byte, node.now)
                for _ in range(30):
                    node.tick()
                self.assertTrue(lib.ecg_link_failed(node.state))
                self.assertEqual(lib.ecg_link_rearm(node.state, node.now), -1)
                self.assertIn(b'BAD_CRC', bytes(node.rx))

    def test_rearm_waits_until_done_has_left_transmit_queue(self):
        for rate, lib in self.libs.items():
            with self.subTest(rate=rate):
                node = link_tests.Node(lib)
                for message in (f'I,ECG-IN-1,queued,{rate},REPLAY,4096', 'F,0'):
                    for byte in encode(message):
                        lib.ecg_link_feed(node.state, byte, node.now)
                self.assertEqual(lib.ecg_link_rearm(node.state, 0), -1)
                for _ in range(30):
                    node.tick()
                self.assertIn(b',DONE,', bytes(node.rx))
                self.assertEqual(lib.ecg_link_rearm(node.state, node.now), 0)

    def test_stop_and_restart_vendor_workers_reuse_same_device(self):
        from ecg_bridge_worker import BridgeWorker
        from ecg_capture_core import FIELDS
        folder = pipeline_tests.PipelineTests.folder / ('reuse_'+uuid.uuid4().hex[:8])
        folder.mkdir()
        source = folder/'source.csv'
        with source.open('x', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            writer.writerows((i/500,8388608,8388608+(20000 if i%400==100 else 0),0,0)
                             for i in range(1500))
        node = ReusableNode(self.libs[500])
        node.close = lambda: None
        worker = BridgeWorker('csv',source,'same_board',folder/'stopped',
                              port_factory=lambda *args:node,pause=0)
        worker.start()
        deadline = time.monotonic()+5
        while worker.is_alive() and worker.capture.snapshot()[0]['total']<32 and time.monotonic()<deadline:
            time.sleep(.002)
        worker.stop()
        worker.join(10)
        self.assertFalse(worker.is_alive())
        info = worker.snapshot()[0]
        self.assertIsNone(info['error'], info)
        self.assertEqual(info['reason'], 'stopped_by_user')
        self.assertTrue(info['done'])
        self.assertGreater(info['confirmed'], 0)
        self.assertLess(info['confirmed'], 1500)
        second = BridgeWorker('csv',source,'same_board',folder/'restarted',realtime=False,
                              port_factory=lambda *args:node,pause=0)
        second.start()
        second.join(15)
        if second.is_alive():
            second.stop()
            second.join(5)
        self.assertFalse(second.is_alive())
        info = second.snapshot()[0]
        self.assertIsNone(info['error'], info)
        self.assertEqual((info['reason'],info['confirmed'],info['echoed']),('completed',1500,1500))
        self.assertEqual(node.rearmed, 2)


if __name__ == '__main__':
    unittest.main()
