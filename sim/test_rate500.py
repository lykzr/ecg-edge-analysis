"""500Hz有理FIR的实际C与独立SciPy参考；不证明QRS质量或实采。"""
import array,ctypes as ct,os,subprocess,sys,unittest,shutil,uuid
from pathlib import Path
import numpy as np
from scipy.signal import firwin,upfirdn
ROOT=Path(__file__).resolve().parents[1]
class RateTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  explicit=os.environ.get('ECG_RATE500_EXE')
  if explicit:cls.exe=Path(explicit);return
  cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
  if not cc:raise RuntimeError('需要已有GCC，不安装')
  folder=ROOT/'tmp/rate500_fir_tests'/uuid.uuid4().hex[:10];folder.mkdir(parents=True,exist_ok=False);cls.exe=folder/('fir.exe' if os.name=='nt' else 'fir')
  args=[cc,'-std=c11','-O2','-ffp-contract=off',str(ROOT/'sim/ecg_rate500_host.c'),str(ROOT/'src/ps/ecg_rate500/rate500.c'),str(ROOT/'src/ps/ecg_runtime/runtime.c'),'-lm','-o',str(cls.exe)]
  p=subprocess.run(args,capture_output=True,env=dict(os.environ,TMP=str(folder),TEMP=str(folder)));(folder/'compile.log').write_bytes(p.stdout+p.stderr)
  if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))

 def compare(self,xs):
  exe=self.exe;p=subprocess.run([str(exe.resolve()),'samples'],input=array.array('h',xs).tobytes(),capture_output=True,check=True)
  rows=[tuple(map(int,s.split(','))) for s in p.stdout.decode().splitlines()]
  expected=upfirdn(firwin(1001,1/25,window=('kaiser',8.6))*18,np.asarray(xs,dtype=float),18,25)
  count=(len(xs)-1)*18//25+1
  expected=expected[:count];expected=np.clip(np.copysign(np.floor(np.abs(expected)+.5),expected),-32768,32767).astype(int)
  self.assertEqual([i for i,y in rows],list(range(count)));np.testing.assert_array_equal([y for i,y in rows],expected)
  return rows
 def test_zero_dc(self):
  self.compare([0]*5000);r=self.compare([1234]*5000);self.assertTrue(all(abs(y-1234)<=2 for i,y in r[60:]))
 def test_fullscale_noise(self):
  self.compare([32767 if i%2 else -32768 for i in range(4000)]);self.compare(np.random.default_rng(1024).integers(-32768,32768,5000).tolist())
 def test_pulse_start_and_no_eof_padding(self):
  for length in (1,2,25,5001):self.compare([16000]+[0]*(length-1))
 def test_prefix_causality(self):
  xs=np.random.default_rng(5).integers(-10000,10000,5000).tolist();short=self.compare(xs[:1701]);long=self.compare(xs);self.assertEqual(short,long[:len(short)])
if __name__=='__main__':unittest.main()
