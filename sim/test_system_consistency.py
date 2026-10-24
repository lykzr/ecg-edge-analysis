"""构建身份、采样率、结束残行与显示一致性回归；不连接板卡。"""
import io,json,hashlib,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'board'),str(ROOT/'src/pc'),str(ROOT/'src')]
from runtime_artifacts import resolve_runtime_artifacts
import rebuild_system
from ecg_runtime_worker import RuntimeWorker
from ecg_bridge_protocol import encode
from ecg_monitor_core import Monitor
from ecg_capture_core import CaptureSample
from ui.plot import draw_trace

class MemoryRecords:
 def __init__(self,*a,**kw):self.monitor=Monitor()
 def write(self,*a):pass
 def row(self,*a):pass
 def close(self,s):self.saved=s
class TailPort:
 def __init__(self,*a):self.rx=b'H,ECG-UART-1,ps-runtime500-ready,boot,UNKNOWN,QRS26-500-ARM,500,4096,0xD\n';self.n=0
 def read(self,n):data=self.rx;self.rx=b'';return data
 def close(self):pass
 def write(self,b):
  f=b.split(b'*')[0].decode().split(',')
  if f[0]=='I':
   self.session=f[2];self.rx+=f'H,ECG-UART-1,ps-runtime500-1,{self.session},REPLAY,QRS26-500-ARM,500,4096,0xD\n'.encode()+encode(f'A,ECG-IN-1,{self.session},0,READY,NA')
  elif f[0]=='D':
   seq=int(f[1]);n=int(f[2]);self.n+=n
   for j in range(0,n,8):
    values=f[3+j:3+min(n,j+8)];self.rx+=f'W,{seq+j},{len(values)},'.encode()+','.join(x+',NA' for x in values).encode()+b'\n'
   self.rx+=encode(f'A,ECG-IN-1,{self.session},{self.n},ACCEPTED,NA')
  else:self.rx+=f'L,I,END reason=completed samples={self.n} events=0\n'.encode()+encode(f'A,ECG-IN-1,{self.session},{self.n},DONE,NA')+b'E,1'
  return len(b)
class ConsistencyTests(unittest.TestCase):
 def test_truncated_usb_tail_is_failure(self):
  data=b'index,sample,fs,scale\n0,0,500,4096\n1,0,500,4096\n'
  with patch('ecg_runtime_worker.BridgeRecords',MemoryRecords),patch.object(Path,'open',return_value=io.BytesIO(data)),patch('ecg_runtime_worker.time.sleep',lambda _:None):
   worker=RuntimeWorker('unused.csv','fake','unused',port_factory=TailPort,realtime=False,sampling_hz=500);worker.run()
  self.assertEqual(worker.info['reason'],'failed');self.assertIn('USB残行',worker.info['error']);self.assertEqual(worker.info['incomplete_rx_bytes'],3)
 def test_plot_uses_selected_rate(self):
  class Canvas:
   def __init__(self):self.text=[]
   def winfo_width(self):return 800
   def winfo_height(self):return 220
   def delete(self,*a,**kw):pass
   def create_line(self,*a,**kw):pass
   def create_text(self,*a,**kw):self.text.append(kw.get('text',''))
  for rate in (360,500):
   c=Canvas();draw_trace(c,[CaptureSample(i,i/rate,8388608,8388608+i) for i in range(3)],'ecg',True,sampling_hz=rate);self.assertIn(str(rate)+'Hz',c.text[-1])
 def base(self):
  p=ROOT/'tmp/consistency_tests';p.mkdir(parents=True,exist_ok=True);return tempfile.TemporaryDirectory(dir=p)
 def test_manifest_selects_new_hardware_and_rejects_mismatch(self):
  with self.base() as folder:
   root=Path(folder);files={}
   for n in ('new/hardware/ecg_system_candidate.bit','new/hardware/ecg_system_candidate.xsa','new/hardware/ps7_init.tcl','new/app.elf'):
    p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(n.encode());files[n]=dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
   m=root/'manifest.json';m.write_text(json.dumps(dict(files=files,sources={},elf='new/app.elf',sampling_hz=360)))
   _,paths=resolve_runtime_artifacts(m,root=root);self.assertEqual(paths['bit'],root/'new/hardware/ecg_system_candidate.bit')
   with self.assertRaisesRegex(ValueError,'采样率'):resolve_runtime_artifacts(m,root=root,expected_rate=500)
   paths['init'].write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'匹配文件'):resolve_runtime_artifacts(m,root=root)
 def test_explicit_rate_overrides_inherited_environment(self):
  with self.base() as folder:
   root=Path(folder);hardware=root/'tmp/hardware';hardware.mkdir(parents=True)
   bd={'design':{'components':{'processing_system7_0':{'parameters':{}},'ecg_qrs_axi_0':{'parameters':{}}}}}
   saved=root/'vivado/ecg_edge/ecg_edge.srcs/sources_1/bd/ecg_system/ecg_system.bd';saved.parent.mkdir(parents=True);saved.write_text(json.dumps(bd));(hardware/'ecg_system.bd').write_text(json.dumps(bd))
   for n in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl'):(hardware/n).write_bytes(b'test')
   seen=[]
   def command(*args,**kw):
    env=kw['env'];seen.append(env['ECG_RUNTIME_RATE']);ws=Path(env['ECG_RUNTIME_WORKSPACE']);ws.mkdir(parents=True)
    (ws/'build_manifest.json').write_text(json.dumps(dict(sampling_hz=int(env['ECG_RUNTIME_RATE']),window_trace=False,elf='fake',build_id='fake')))
    return type('Result',(),dict(returncode=0))()
   with patch.object(rebuild_system,'ROOT',root),patch.object(rebuild_system.subprocess,'run',side_effect=command),patch.dict(os.environ,ECG_RUNTIME_RATE='500'):
    rebuild_system.run(root/'tmp/out','vivado','vitis',hardware,rate=360)
   self.assertEqual(seen,['360']);self.assertEqual(json.loads((root/'tmp/out/summary.json').read_text())['sampling_hz'],360)
if __name__=='__main__':unittest.main()
