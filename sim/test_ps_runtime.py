"""实际C逐样本移植/切拍参考核验；只使用受控输入，不恢复调参。"""
import ctypes as ct
from dataclasses import asdict
import os
from pathlib import Path
import shutil,subprocess,sys,unittest,uuid
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/reference'),str(ROOT/'src/pc')]
from ecg_signal_pipeline import SignalPipeline
from ecg_classifier import prepare
from test_classifier import spec
from test_classification_ps import Req
class PortTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
  if not cc:raise RuntimeError('需要已有GCC，不自动安装')
  cls.folder=ROOT/'tmp/system_port_tests'/uuid.uuid4().hex[:10];cls.folder.mkdir(parents=True,exist_ok=False)
  dll=cls.folder/('port.dll' if os.name=='nt' else 'port.so')
  args=[cc,'-shared','-std=c11','-O2','-ffp-contract=off','-I'+str(ROOT/'src/ps/ecg_classification')]+([] if os.name=='nt' else ['-fPIC'])+[str(ROOT/'src/ps/ecg_runtime'/n) for n in ('runtime.c','pipeline.c')]+[str(ROOT/'src/ps/ecg_classification/classification.c'),'-o',str(dll)]
  p=subprocess.run(args,capture_output=True,env=dict(os.environ,TMP=str(cls.folder),TEMP=str(cls.folder)));(cls.folder/'compile.log').write_bytes(p.stdout+p.stderr)
  if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
  cls.lib=ct.CDLL(str(dll));L=cls.lib;L.ecg_pipeline_size.restype=ct.c_size_t
  L.ecg_pipeline_init.argtypes=[ct.c_void_p,ct.c_uint32,ct.POINTER(ct.c_float),ct.POINTER(ct.c_float)]
  L.ecg_pipeline_push.argtypes=[ct.c_void_p,ct.c_int16,ct.c_uint32,ct.POINTER(Req)]
  L.ecg_pipeline_finish.argtypes=[ct.c_void_p,ct.POINTER(Req)]
 def setup(self):
  self.state=ct.create_string_buffer(self.lib.ecg_pipeline_size());self.out=(Req*32)();self.spec=spec()
  self.assertEqual(self.lib.ecg_pipeline_init(self.state,1,(ct.c_float*3)(*self.spec.rr_mean),(ct.c_float*3)(*self.spec.rr_std)),0)
 def compare(self,xs):
  self.setup();py=SignalPipeline(360);requests=[];events=0;expected={}
  for n,x in enumerate(xs):
   ev,beats=py.push(x,sequence=n)
   for _,pos,rr in ev:events+=1;expected[pos]=events
   for beat in beats:
    r=prepare(beat,'unit',expected[beat.position],self.spec);requests.append(r)
   count=self.lib.ecg_pipeline_push(self.state,x,n,self.out);self.assertGreaterEqual(count,0)
   for j in range(count):
    a=self.out[j];r=requests.pop(0)
    self.assertEqual((a.beat_id,a.position,a.rr_samples,a.sampling_hz,a.ready_at),(r.beat_id,r.position,r.rr_samples,r.sampling_hz,r.ready_at))
    self.assertEqual(a.input_status,2 if r.status=='MISSING_RR' else 0)
    np.testing.assert_allclose(a.waveform,r.waveform,atol=1e-6,rtol=1e-6)
    if r.rr:np.testing.assert_allclose(a.rr,r.rr,atol=1e-6,rtol=1e-6)
  self.assertFalse(requests)
  return events
 def test_zero_and_dc(self):
  self.assertEqual(self.compare([0]*3000),0);self.assertEqual(self.compare([2000]*3000),0)
 def test_positive_negative_and_mixed_pulses(self):
  for sign in (1,-1):
   xs=[sign*(18000 if i%288==150 else 0) for i in range(4500)]
   self.assertGreater(self.compare(xs),8)
 def test_broad_and_biphasic_waveforms(self):
  xs=[int(16000*np.exp(-.5*((i%288-150)/5)**2)-6000*np.exp(-.5*((i%288-161)/6)**2)) for i in range(4000)]
  self.assertGreater(self.compare(xs),6)
 def test_fullscale_and_seeded_noise(self):
  self.compare([32767 if i%2 else -32768 for i in range(3000)])
  rng=np.random.default_rng(1024)
  self.compare([int(x) for x in rng.integers(-32768,32768,4000)])
 def test_gap_rejected_and_reset(self):
  self.setup();self.assertEqual(self.lib.ecg_pipeline_push(self.state,1,0,self.out),0)
  self.assertEqual(self.lib.ecg_pipeline_push(self.state,2,2,self.out),-1)
  self.assertEqual(self.lib.ecg_pipeline_init(self.state,2,(ct.c_float*3)(0,0,0),(ct.c_float*3)(1,1,1)),0)
  self.assertEqual(self.lib.ecg_pipeline_push(self.state,0,0,self.out),0)
 def test_finish_no_padding_or_reuse(self):
  self.setup()
  for i in range(100):self.assertEqual(self.lib.ecg_pipeline_push(self.state,0,i,self.out),0)
  self.assertEqual(self.lib.ecg_pipeline_finish(self.state,self.out),0)
  self.assertEqual(self.lib.ecg_pipeline_push(self.state,0,100,self.out),-1)
  self.assertEqual(self.lib.ecg_pipeline_finish(self.state,self.out),-1)
if __name__=='__main__':unittest.main()
