"""500Hz验板结果解析回归；只读人工小例子，不连接板卡。"""
import sys,tempfile,unittest,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'board'),str(ROOT/'data')]
from verify_runtime500 import check_output
from verify_pipeline500 import DT
class ResultTests(unittest.TestCase):
 def run_text(self,text,requests,trace=False):
  base=ROOT/'tmp/runtime500_result_tests';base.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=base) as folder:
   p=Path(folder)/'uart.log';p.write_text(text);return check_output(p,requests,trace)
 def req(self,status=2):
  r=np.zeros(1,dtype=DT);r[0]['beat_id']=1;r[0]['position']=250;r[0]['ready_at']=600;r[0]['input_status']=status;r[0]['waveform']=np.arange(128,dtype=np.float32);return r
 def text(self,status=2):return f'E,1,250,0,-1,?,-1\nL,I,CLASS evt=1 state={status} ready=600\n'
 def test_unknown_result_and_exact_state(self):self.assertEqual(self.run_text(self.text(),self.req())['events'],1)
 def test_wrong_position_rejected(self):
  with self.assertRaises(ValueError):self.run_text(self.text().replace('250','251'),self.req())
 def test_missing_state_rejected(self):
  with self.assertRaises(ValueError):self.run_text('E,1,250,0,-1,?,-1\n',self.req())
 def trace(self):
  return ''.join('L,I,WIN evt=1 offset='+str(i)+' '+' '.join(f'{struct.unpack("<I",struct.pack("<f",float(j)))[0]:08X}' for j in range(i,i+8))+'\n' for i in range(0,128,8))
 def test_complete_window_trace(self):
  r=self.run_text(self.text()+self.trace(),self.req(),True);self.assertEqual(r['windows_compared'],1);self.assertEqual(r['max_window_absolute_error'],0)
 def test_trace_forbidden_when_disabled(self):
  with self.assertRaises(ValueError):self.run_text(self.text()+self.trace(),self.req(),False)
 def test_incomplete_window_must_not_trace(self):
  with self.assertRaises(ValueError):self.run_text(self.text(4)+self.trace(),self.req(4),True)
if __name__=='__main__':unittest.main()
