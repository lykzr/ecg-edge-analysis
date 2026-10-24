"""360Hz界面后台对实际C核心；假串口，不替代实板/视觉验收。"""
import csv,json,sys,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'src')]
from ecg_runtime_worker import RuntimeWorker
import test_runtime_link as link_tests
class WorkerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):link_tests.LinkTests.setUpClass();cls.lib=link_tests.LinkTests.lib
 def folder(self):
  p=ROOT/'tmp/runtime_worker_tests'/uuid.uuid4().hex[:10];p.mkdir(parents=True,exist_ok=False);return p
 def csv(self,path,count,rate=360):
  with path.open('x',newline='') as f:
   w=csv.writer(f);w.writerow(['index','sample','fs','scale']);w.writerows((i,18000 if i%288==150 else 0,rate,4096) for i in range(count))
 def worker(self,folder,count=100,rate=360,fault=False):
  self.csv(folder/'input.csv',count,rate)
  node=link_tests.Node(self.lib);node.close=lambda:None
  if fault:
   def fail(n):raise OSError('断连注入')
   node.read=fail
  return RuntimeWorker(folder/'input.csv','COM1',folder/'out',port_factory=lambda _:node,realtime=False)
 def test_partial_final_batch_and_record(self):
  folder=self.folder();w=self.worker(folder,105);w.start();w.join(10);self.assertFalse(w.is_alive())
  info,capture,_,_=w.snapshot();self.assertIsNone(info['error']);self.assertEqual(info['reason'],'completed');self.assertEqual((info['confirmed'],capture['total']),(105,105))
  self.assertEqual((folder/'input.csv').read_bytes(),(folder/'out/input.csv').read_bytes())
 def test_reject_vendor_rate_in_native_path(self):
  folder=self.folder();w=self.worker(folder,32,500);w.start();w.join(10);self.assertFalse(w.is_alive());self.assertIn('采样率',w.snapshot()[0]['error'])
 def test_disconnect_preserves_error_and_output(self):
  folder=self.folder();w=self.worker(folder,32,fault=True);w.start();w.join(10);self.assertFalse(w.is_alive());self.assertIn('断连注入',w.snapshot()[0]['error']);self.assertTrue((folder/'out/summary.json').is_file())
 def test_native_hidden_ui_uses_source_rate(self):
  import tkinter as tk
  from ui.bridge import BridgePanel
  folder=self.folder();w=self.worker(folder,333);w.start();w.join(10);self.assertFalse(w.is_alive())
  root=tk.Tk();root.withdraw()
  try:
   p=BridgePanel(root);p.window.withdraw();p.worker=w;p.tick();root.update_idletasks()
   self.assertIn('360Hz',p.native_button.cget('text'))
   self.assertIn('标准CSV',p.details.get())
   self.assertIn('完整运行结束',p.state.get())
   p.window.destroy()
  finally:root.destroy()
 def test_stop_without_board_boot_exits(self):
  class Quiet:
   def read(self,n):return b''
   def write(self,data):raise AssertionError('未就绪不能上传')
   def close(self):pass
  folder=self.folder();self.csv(folder/'input.csv',32)
  w=RuntimeWorker(folder/'input.csv','COM1',folder/'out',port_factory=lambda _:Quiet(),realtime=False)
  w.stop();w.start();w.join(2);self.assertFalse(w.is_alive());self.assertEqual(w.snapshot()[0]['reason'],'stopped_by_user')
 def test_stop_prefix_then_new_session(self):
  folder=self.folder();w=self.worker(folder,3200);w.stop();w.start();w.join(10);self.assertFalse(w.is_alive());self.assertEqual(w.snapshot()[0]['reason'],'stopped_by_user')
  folder=self.folder();w=self.worker(folder,33);w.start();w.join(10);self.assertFalse(w.is_alive());self.assertEqual(w.snapshot()[0]['confirmed'],33)
if __name__=='__main__':unittest.main()
