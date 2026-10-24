"""实际C链路与PC客户机离线闭环；不是物理串口。"""
import ctypes as ct
from collections import deque
import os,shutil,subprocess,sys,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'src/reference')]
from ecg_bridge_core import BridgeClient
from ecg_bridge_protocol import encode
from ecg_monitor_core import Monitor
from ecg_qrs_runtime import ResearchRuntime
import test_ps_runtime as runtime_tests
READY=ct.CFUNCTYPE(ct.c_int,ct.c_void_p);BYTE=ct.CFUNCTYPE(None,ct.c_void_p,ct.c_ubyte)
class Io(ct.Structure):_fields_=[('ctx',ct.c_void_p),('ready',READY),('byte',BYTE)]
class Node:
 def __init__(self,lib,trace=0):
  self.lib=lib;self.now=0;self.rx=deque();self.state=ct.create_string_buffer(lib.ecg_link_size());self.pipeline=ct.create_string_buffer(lib.ecg_pipeline_size())
  self.callbacks=(READY(lambda _:1),BYTE(lambda _,x:self.rx.append(x)));self.io=Io(None,*self.callbacks);lib.ecg_link_init(self.state,self.io,self.pipeline,trace)
 def tick(self):self.now+=100;return self.lib.ecg_link_step(self.state,self.now)
 def read(self,n):self.tick();return bytes(self.rx.popleft() for _ in range(min(n,len(self.rx))))
 def write(self,data):
  data=data[:7]
  for x in data:self.lib.ecg_link_feed(self.state,x,self.now)
  return len(data)
class LinkTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  runtime_tests.PortTests.setUpClass();folder=runtime_tests.PortTests.folder;cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc');dll=folder/'link.dll'
  args=[cc]+([] if os.name=='nt' else ['-fPIC'])+['-shared','-std=c11','-O2','-ffp-contract=off','-I'+str(ROOT/'src/ps/ecg_classification')]+[str(ROOT/'src/ps/ecg_runtime'/n) for n in ('runtime.c','pipeline.c','link.c')]+[str(ROOT/'src/ps/ecg_classification/classification.c'),str(ROOT/'sim/ecg_runtime_link_host.c'),'-o',str(dll)]
  p=subprocess.run(args,capture_output=True,env=dict(os.environ,TMP=str(folder),TEMP=str(folder)));(folder/'link_compile.log').write_bytes(p.stdout+p.stderr)
  if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
  cls.lib=ct.CDLL(str(dll));L=cls.lib
  L.ecg_link_size.restype=ct.c_size_t;L.ecg_pipeline_size.restype=ct.c_size_t
  L.ecg_link_init.argtypes=[ct.c_void_p,Io,ct.c_void_p,ct.c_uint]
  L.ecg_link_feed.argtypes=[ct.c_void_p,ct.c_ubyte,ct.c_uint64];L.ecg_link_step.argtypes=[ct.c_void_p,ct.c_uint64]
 def run_client(self,xs,trace=0):
  node=Node(self.lib,trace);m=Monitor();c=BridgeClient(node,m,'unit','REPLAY',profile='runtime360',clock=lambda:node.now/1e6,timeout=10)
  c.add(xs);c.finish_source()
  for i in range(300000):
   c.pump()
   if c.done:break
  self.assertTrue(c.done);self.assertEqual((c.confirmed,c.echoed),(len(xs),len(xs)));return m
 def test_real_c_full_duplex_and_window_trace(self):
  xs=[18000 if i%288==150 else 0 for i in range(3000)]
  m=self.run_client(xs,1);py=ResearchRuntime();ev=[]
  for x in xs:ev.extend(py.push(x))
  self.assertEqual([(e.pos,e.rr) for e in m.events],[(e[1],e[2]) for e in ev]);self.assertTrue(all(e.cls=='?' for e in m.events));self.assertEqual(m.decoder.counts['invalid'],0)
 def test_no_upload_before_boot_ready(self):
  class Quiet:
   def read(self,n):return b''
   def write(self,data):raise AssertionError('未就绪不能上传')
  c=BridgeClient(Quiet(),Monitor(),'unit','REPLAY',profile='runtime360')
  c.add([0]*32);c.pump();self.assertFalse(c.started)
 def test_missing_boot_has_bounded_timeout(self):
  class Quiet:
   def read(self,n):return b''
   def write(self,data):raise AssertionError('未就绪不能上传')
  t=[0.];c=BridgeClient(Quiet(),Monitor(),'unit','REPLAY',profile='runtime360',clock=lambda:t[0],timeout=10)
  t[0]=10.
  with self.assertRaises(TimeoutError):c.pump()
 def test_zero_and_new_session(self):
  self.assertEqual(self.run_client([0]*100).counts['events'],0);self.assertEqual(self.run_client([1]*100).counts['events'],0)
 def test_wrong_rate_contract_rejected(self):
  node=Node(self.lib);m=Monitor();c=BridgeClient(node,m,'unit','REPLAY',clock=lambda:node.now/1e6)
  with self.assertRaises((OSError,ValueError)):
   for i in range(1000):c.pump()
 def test_crc_partial_and_idle_faults(self):
  for mode in ('crc','partial','idle'):
   node=Node(self.lib)
   def send(data):
    for b in data:self.lib.ecg_link_feed(node.state,b,node.now)
   send(encode('I,ECG-IN-1,unit,360,REPLAY,4096'));node.tick();node.rx.clear()
   if mode=='crc':send(b'D,0,1,0*00000000\n')
   if mode=='partial':send(b'D,0,')
   node.now+=6000000
   for _ in range(100):node.tick()
   text=bytes(node.rx);self.assertIn({'crc':b'BAD_CRC','partial':b'PARTIAL_TIMEOUT','idle':b'INPUT_TIMEOUT'}[mode],text);self.assertFalse(any(line.startswith(b'W,') for line in text.splitlines()))
if __name__=='__main__':unittest.main()
