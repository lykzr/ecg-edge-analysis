"""唯一板卡的冻结360Hz数字回放验收；不写Flash，不冒称无线/500Hz。"""
import argparse,json,subprocess,sys,time,uuid,re,struct,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'src/reference'),str(ROOT/'data')]
from ecg_ports import enumerate_ports,validate_port
from ecg_bridge_serial import DuplexSerial
from ecg_bridge_core import BridgeClient
from ecg_bridge_records import BridgeRecords
from ecg_signal_pipeline import SignalPipeline
from ecg_dataset import load_record,digest

def run(manifest,xsdb,cable,port,identity,record,seconds,output,raw):
 m=json.loads(manifest.read_text());protocol=json.loads((ROOT/'data/qrs_runtime_protocol.json').read_text())
 if record not in protocol['development_records']+protocol['evaluation_records']:raise ValueError('只允许已有已知开发数据')
 if not 1<=seconds<=1800:raise ValueError('时长1..1800')
 for n,v in m['files'].items():
  p=(ROOT/n).resolve();p.relative_to(ROOT)
  if p.stat().st_size!=v['bytes'] or digest(p)!=v['sha256']:raise ValueError('匹配文件不符')
 for n,v in m['sources'].items():
  if digest(ROOT/n)!=v:raise ValueError('当前源与ELF不符')
 ports,warnings=enumerate_ports();device=validate_port(port,dict(device_id=identity),ports)
 if not identity or not device['candidate']:raise ValueError('需要明确USB实例')
 xs,_,meta=load_record(raw,record,'MLII');xs=xs[:int(seconds*360)]
 pipeline=SignalPipeline(360);expected=[];windows={}
 for n,x in enumerate(xs):
  events,beats=pipeline.push(x,sequence=n);expected.extend(events)
  for beat in beats:windows[beat.position]=beat.model_input()[0]
 pipeline.finish()
 records=BridgeRecords(output);serial=None;report=dict(passed=False,scope='ARM frozen360 QRS/window digital UART replay; no CNN/wireless/500Hz',record=record,input=meta,manifest=m,uart=device)
 (output/'plan.json').write_text(json.dumps(report,indent=2)+'\n')
 try:
  serial=DuplexSerial(port)
  hw=ROOT/'releases/latest/smoke/hardware'
  args=[str(xsdb),str(ROOT/'board/classification_handoff/run.tcl'),cable,str(hw/'ecg_system_candidate.bit'),str(hw/'ps7_init.tcl'),str(ROOT/m['elf'])]
  with (output/'jtag.log').open('xb') as log:
   process=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=90,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if process.returncode or 'ECG_CLASS_JTAG_STARTED' not in (output/'jtag.log').read_text(errors='replace'):raise RuntimeError('JTAG未完成，不发送样本')
  client=BridgeClient(serial,records.monitor,uuid.uuid4().hex,'REPLAY',profile='runtime360',timeout=10,write_log=records.write)
  produced=0;origin=None;start=time.monotonic()
  while time.monotonic()-start<len(xs)/360+30:
   if client.started and client.waiting is None and origin is None:origin=time.monotonic()
   if origin is not None and not client.eof:
    due=min(len(xs),int((time.monotonic()-origin)*360)+1)
    values=xs[produced:due]
    if values:
     client.add(values)
     for n,x in enumerate(values,produced):records.row('normalized.csv',[n,x])
     produced=due
    if produced==len(xs):client.finish_source()
   client.pump()
   if client.done:break
   time.sleep(.001)
  if not client.done:raise TimeoutError('回放未收完整END/DONE')
  events=[(e.pos,e.rr) for e in records.monitor.events]
  # 显示缓存只有256事件；完整记录中的E独立读取，不能只验屏幕缓存。
  full=(output/'results/raw.log').read_text();event_rows=[];trace={}
  for line in full.splitlines():
   if line.startswith('E,'):
    f=line.split(',');event_rows.append((int(f[1]),int(f[2]),int(f[3]),f[5]))
   match=re.fullmatch(r'L,I,WIN evt=(\d+) offset=(\d+)((?: [0-9A-F]{8}){8})',line)
   if match:
    eid,offset=int(match[1]),int(match[2]);values=[struct.unpack('<f',struct.pack('<I',int(x,16)))[0] for x in match[3].split()]
    if (eid,offset) in trace:raise ValueError('重复窗口分块')
    trace[eid,offset]=values
  if [(i,p,rr) for i,p,rr,c in event_rows]!=[(i+1,p,rr) for i,(_,p,rr) in enumerate(expected)]:raise ValueError('ARM与参考事件不一致')
  if any(c!='?' for _,_,_,c in event_rows):raise ValueError('无模型不能提供类别')
  errors=[];compared=0
  for eid,pos,rr,c in event_rows:
   if pos not in windows:continue
   native=np.asarray([v for j in range(0,128,8) for v in trace[eid,j]],dtype=np.float32)
   error=float(np.max(np.abs(native-windows[pos])));errors.append(error)
   np.testing.assert_allclose(native,windows[pos],atol=1e-6,rtol=1e-6);compared+=1
  report.update(client.summary(),passed=True,reason='completed',events=len(event_rows),windows_compared=compared,max_window_absolute_error=max(errors,default=0),elapsed_s=time.monotonic()-start)
 except Exception as exc:report.update(error=type(exc).__name__+': '+str(exc),reason='failed')
 finally:
  if serial is not None:serial.close()
  records.close(report)
 print(json.dumps({k:v for k,v in report.items() if k not in ('manifest','input','uart')}))
 if not report['passed']:raise RuntimeError('实板未通过，保留现场')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('manifest','xsdb','output','raw'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('cable','port','device-id'):p.add_argument('--'+n,required=True)
 p.add_argument('--record',default='100');p.add_argument('--seconds',type=float,default=30)
 a=p.parse_args();run(a.manifest,a.xsdb,a.cable,a.port,a.device_id,a.record,a.seconds,a.output,a.raw)
