"""主体离线边界：真实C链路/记录，不等于真实串口验收。"""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'src/reference')]
import test_runtime_worker as worker_tests
from ecg_runtime_worker import RuntimeWorker
from ecg_metrics import StageMetrics
from ecg_bridge_capture import InputConverter
from ecg_bridge_core import BridgeClient
from ecg_monitor_core import Monitor

class EdgeTests(worker_tests.WorkerTests):
    # 继承原六项共同回归；另加八项边界检查。
    def test_limit_stops_and_keeps_summary(self):
        folder=self.folder();self.csv(folder/'input.csv',300)
        node=worker_tests.link_tests.Node(self.lib);node.close=lambda:None
        w=RuntimeWorker(folder/'input.csv','fake',folder/'out',port_factory=lambda _:node,realtime=False,maximum=1024)
        w.start();w.join(10);self.assertFalse(w.is_alive())
        info=json.loads((folder/'out/summary.json').read_text(encoding='utf-8'))
        self.assertEqual(info['reason'],'failed');self.assertIn('限额',info['error']);self.assertLessEqual(info['data_bytes'],1024)
    def test_stop_during_transfer_drains_prefix(self):
        folder=self.folder();w=self.worker(folder,2000);node=worker_tests.link_tests.Node(self.lib)
        original=node.read
        def read(n):
            if w.snapshot()[0]['confirmed']>=32:w.stop()
            return original(n)
        node.read=read;node.close=lambda:None;w.port_factory=lambda _:node
        w.start();w.join(10);self.assertFalse(w.is_alive())
        info=w.snapshot()[0];self.assertIsNone(info['error']);self.assertEqual(info['reason'],'stopped_by_user')
        self.assertLess(info['confirmed'],2000);self.assertEqual(info['source_samples'],info['confirmed']);self.assertEqual(info['echoed'],info['confirmed'])
    def test_close_error_persists_failed_summary(self):
        from ecg_bridge_records import BridgeRecords
        folder=self.folder();r=BridgeRecords(folder/'out')
        with patch.object(r.monitor,'finish',side_effect=OSError('保存错误注入')):
            with self.assertRaises(OSError):r.close(dict(reason='completed',error=None))
        info=json.loads((folder/'out/summary.json').read_text(encoding='utf-8'))
        self.assertEqual(info['reason'],'failed');self.assertIn('保存错误',info['error'])
        self.assertTrue(all(s.closed for s in r.files.values()))
        self.assertTrue(all(s.closed for s in r.monitor.recorder.files.values()))
    def test_snapshot_is_bounded_and_disk_complete(self):
        folder=self.folder();w=self.worker(folder,4201);w.start();w.join(20);self.assertFalse(w.is_alive())
        info,cap,x,result=w.snapshot();self.assertIsNone(info['error']);self.assertEqual(len(x),4096)
        self.assertEqual((cap['total'],info['confirmed'],info['echoed']),(4201,4201,4201))
        self.assertEqual(len((folder/'out/normalized.csv').read_text().splitlines()),4202)
        self.assertEqual(info['timing']['batch_roundtrip']['count'],132)
    def test_source_gap_is_failure(self):
        folder=self.folder();w=self.worker(folder,35)
        p=folder/'input.csv';s=p.read_text();p.write_text(s.replace('12,','13,',1))
        w.start();w.join(10);self.assertFalse(w.is_alive());self.assertIn('序号',w.snapshot()[0]['error'])
        self.assertEqual(w.snapshot()[0]['reason'],'failed')
    def test_write_failure_saved_and_port_closed(self):
        folder=self.folder();w=self.worker(folder,32);closed=[];node=worker_tests.link_tests.Node(self.lib)
        def fail(data):raise OSError('写错误注入')
        node.write=fail;node.close=lambda:closed.append(1);w.port_factory=lambda _:node
        w.start();w.join(10);self.assertFalse(w.is_alive());self.assertIn('写错误',w.snapshot()[0]['error']);self.assertEqual(closed,[1])
        self.assertTrue((folder/'out/summary.json').is_file())
    def test_metrics_constant_memory_and_reversed_clock(self):
        m=StageMetrics(max_stages=2)
        for i in range(10000):m.record('qrs',.001)
        m.record('transport',2);self.assertEqual(m.summary()['qrs']['count'],10000)
        with self.assertRaises(BufferError):m.record('third',1)
        for value in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):m.record('qrs',value)
    def test_conversion_and_capacity_no_silent_drop(self):
        c=InputConverter(2,8)
        self.assertEqual([c.convert((0,v)) for v in (-8388608,-1,0,8388607)],[-32768,-1,0,32767])
        class Quiet:pass
        b=BridgeClient(Quiet(),Monitor(),'edge','REPLAY',capacity=32);b.add([0]*32)
        with self.assertRaises(BufferError):b.add([1])
        self.assertEqual(b.received,32);self.assertEqual(len(b.queue),32)
if __name__=='__main__':unittest.main()
