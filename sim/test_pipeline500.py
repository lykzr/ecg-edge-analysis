"""实际500Hz C全流程与现有源窗口/RR参考、UART/PC配对；不替代实板。"""
import ctypes as ct,os,sys,subprocess,shutil,uuid,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src/reference'),str(ROOT/'src/pc'),str(ROOT/'build')]
from generate_rate500_runtime import run as generate
from ecg_beat_window import BeatWindow
from test_classification_ps import Req
from test_runtime_link import Node,Io
from ecg_bridge_core import BridgeClient
from ecg_monitor_core import Monitor
from ecg_bridge_protocol import encode
class PipelineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.folder=ROOT/'tmp/rate500_tests'/uuid.uuid4().hex[:10];generate(cls.folder);cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
  if not cc:raise RuntimeError('需要已有GCC，不安装')
  dll=cls.folder/('rate500.dll' if os.name=='nt' else 'rate500.so')
  src=[ROOT/'src/ps/ecg_rate500'/n for n in ('pipeline500.c','rate500.c')]+[cls.folder/'runtime500_bridge.c',cls.folder/'link500.c',ROOT/'src/ps/ecg_classification/classification.c',ROOT/'sim/ecg_runtime_link_host.c']
  args=[cc,'-shared','-std=c11','-O2','-ffp-contract=off']+([] if os.name=='nt' else ['-fPIC'])+['-I'+str(ROOT/'src/ps'/n) for n in ('ecg_classification','ecg_runtime','ecg_rate500')]+[str(p) for p in src]+['-lm','-o',str(dll)]
  p=subprocess.run(args,capture_output=True,env=dict(os.environ,TMP=str(cls.folder),TEMP=str(cls.folder)));(cls.folder/'compile.log').write_bytes(p.stdout+p.stderr)
  if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
  cls.lib=ct.CDLL(str(dll));L=cls.lib;L.ecg_pipeline_size.restype=ct.c_size_t;L.ecg_link_size.restype=ct.c_size_t
  L.ecg_pipeline_init.argtypes=[ct.c_void_p,ct.c_uint32,ct.POINTER(ct.c_float),ct.POINTER(ct.c_float)];L.ecg_pipeline_push.argtypes=[ct.c_void_p,ct.c_int16,ct.c_uint32,ct.POINTER(Req)];L.ecg_pipeline_finish.argtypes=[ct.c_void_p,ct.POINTER(Req)]
  L.ecg_link_init.argtypes=[ct.c_void_p,Io,ct.c_void_p,ct.c_uint];L.ecg_link_feed.argtypes=[ct.c_void_p,ct.c_ubyte,ct.c_uint64];L.ecg_link_step.argtypes=[ct.c_void_p,ct.c_uint64]
 def signal(self,n=6000):return [int(14000*np.exp(-.5*((i%500-250)/7.)**2)-4500*np.exp(-.5*((i%500-265)/9.)**2)) for i in range(n)]
 def requests(self,xs):
  L=self.lib;state=ct.create_string_buffer(L.ecg_pipeline_size());zero=(ct.c_float*3)(0,0,0);one=(ct.c_float*3)(1,1,1);self.assertEqual(L.ecg_pipeline_init(state,1,zero,one),0);out=(Req*32)();rows=[]
  for seq,x in enumerate(xs):
   n=L.ecg_pipeline_push(state,int(x),seq,out);self.assertGreaterEqual(n,0)
   rows.extend(Req.from_buffer_copy(out[j]) for j in range(n))
  n=L.ecg_pipeline_finish(state,out);self.assertGreaterEqual(n,0);rows.extend(Req.from_buffer_copy(out[j]) for j in range(n));return rows
 def test_source_window_and_rr_match(self):
  for sign in (1,-1):
   xs=[sign*x for x in self.signal()];rows=self.requests(xs);self.assertGreater(len(rows),7);history=[];last=None;valid=0
   for r in rows:
    self.assertEqual(r.sampling_hz,500);self.assertLessEqual(r.position,r.ready_at);self.assertEqual(r.rr_samples,0 if last is None else r.position-last);last=r.position
    if r.rr_samples:history.append(r.rr_samples)
    if r.input_status==4:continue
    beat=BeatWindow(r.position,r.ready_at,r.rr_samples,500,178,tuple(xs[r.position-178:r.position+267]),tuple(history[-401:]));wave,basic=beat.model_input()
    np.testing.assert_allclose(r.waveform,wave,atol=1e-6,rtol=1e-6)
    if basic is not None:np.testing.assert_allclose(r.rr,basic,atol=1e-6,rtol=1e-6)
    valid+=1
   self.assertGreater(valid,6)
 def test_zero_memory_gap_reset_and_finish(self):
  self.assertLessEqual(self.lib.ecg_pipeline_size(),192*1024);self.assertFalse(self.requests([0]*6000));state=ct.create_string_buffer(self.lib.ecg_pipeline_size());z=(ct.c_float*3)(0,0,0);o=(ct.c_float*3)(1,1,1);out=(Req*32)()
  self.assertEqual(self.lib.ecg_pipeline_init(state,1,z,o),0);self.assertEqual(self.lib.ecg_pipeline_push(state,0,1,out),-1);self.assertEqual(self.lib.ecg_pipeline_push(state,0,0,out),0);self.assertEqual(self.lib.ecg_pipeline_finish(state,out),0);self.assertEqual(self.lib.ecg_pipeline_push(state,0,1,out),-1)
 def test_prefix_no_future_no_tail_padding(self):
  xs=self.signal(8000);short=self.requests(xs[:3200]);long=self.requests(xs)
  def rows(rs):return [(r.beat_id,r.position,r.rr_samples,r.ready_at,tuple(r.waveform)) for r in rs if r.input_status!=4]
  self.assertEqual(rows(short),[r for r in rows(long) if r[3]<3200])
 def client(self,xs):
  node=Node(self.lib);m=Monitor();c=BridgeClient(node,m,'unit','REPLAY',profile='runtime500',clock=lambda:node.now/1e6,timeout=10)
  c.add(xs);c.finish_source()
  for _ in range(300000):
   c.pump()
   if c.done:break
  self.assertTrue(c.done);self.assertEqual(c.confirmed,len(xs));self.assertEqual(c.echoed,len(xs));return m
 def test_c_uart_pc_full_duplex(self):
  xs=self.signal(3000);m=self.client(xs);expected=self.requests(xs);self.assertEqual([(e.pos,e.rr) for e in m.events],[(r.position,r.rr_samples) for r in expected]);self.assertEqual(m.header.fs,500);self.assertTrue(all(e.cls=='?' for e in m.events))
 def test_worker500_csv_and_wrong_rate(self):
  import csv,json
  from ecg_runtime_worker import RuntimeWorker
  for rate,ok in ((500,True),(360,False)):
   folder=self.folder/('worker_'+str(rate));folder.mkdir();source=folder/'input.csv'
   with source.open('w',newline='') as stream:
    w=csv.writer(stream);w.writerow(['index','sample','fs','scale']);w.writerows((i,x,rate,4096) for i,x in enumerate(self.signal(1500)))
   node=Node(self.lib);node.close=lambda:None
   worker=RuntimeWorker(source,'fake',folder/'out',port_factory=lambda _:node,realtime=False,sampling_hz=500);worker.start();worker.join(10);self.assertFalse(worker.is_alive());info=worker.snapshot()[0]
   self.assertEqual(info['reason'],'completed' if ok else 'failed')
   if ok:self.assertEqual((info['confirmed'],info['echoed']),(1500,1500));self.assertEqual(info['profile'],'runtime500')
 def test_hidden_ui500_control(self):
  import tkinter as tk
  from unittest.mock import patch
  sys.path.insert(0,str(ROOT/'src'));from ui.bridge import BridgePanel
  root=tk.Tk();root.withdraw()
  try:
   with patch('ui.bridge.enumerate_ports',return_value=([],[])):
    panel=BridgePanel(root);self.assertIn('500Hz',panel.rate500_button.cget('text'));panel.tick();self.assertEqual(str(panel.rate500_button.cget('state')),'normal');panel.window.destroy()
  finally:root.destroy()
 def test_wrong360_crc_gap_timeout_rejected(self):
  for mode in ('rate','crc','gap','timeout'):
   node=Node(self.lib)
   def send(data):
    for b in data:self.lib.ecg_link_feed(node.state,b,node.now)
   send(encode('I,ECG-IN-1,unit,'+('360' if mode=='rate' else '500')+',REPLAY,4096'))
   for _ in range(100):node.tick()
   if mode=='crc':send(b'D,0,1,0*00000000\n')
   if mode=='gap':send(encode('D,1,1,0'))
   if mode=='timeout':node.now+=6000000
   for _ in range(300):node.tick()
   text=bytes(node.rx);self.assertIn({'rate':b'BAD_INIT','crc':b'BAD_CRC','gap':b'BAD_SEQUENCE','timeout':b'INPUT_TIMEOUT'}[mode],text)
if __name__=='__main__':unittest.main()
