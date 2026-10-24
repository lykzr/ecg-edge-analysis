"""500Hz应用临时JTAG数字验收；实际事件与C参考/模型窗口对照，不写Flash。"""
import argparse,csv,json,subprocess,sys,time,uuid,re,struct,hashlib,shutil,os
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'src/reference'),str(ROOT/'data'),str(ROOT/'build')]
from runtime_artifacts import resolve_runtime_artifacts
from ecg_ports import enumerate_ports,validate_port
from ecg_bridge_serial import DuplexSerial
from ecg_bridge_core import BridgeClient
from ecg_bridge_records import BridgeRecords
from ecg_runtime_worker import RuntimeWorker
from ecg_dataset import load_record,digest
from verify_pipeline500 import DT
from generate_rate500_runtime import run as generate


def prepare(folder,raw):
 folder=Path(folder).resolve();folder.relative_to(ROOT/'tmp');folder.mkdir(parents=True,exist_ok=False)
 generated=folder/'generated';generate(generated)
 sources=[ROOT/'src/ps/ecg_rate500'/n for n in ('pipeline500.c','rate500.c')]+[generated/'runtime500_bridge.c',ROOT/'src/ps/ecg_classification/classification.c',ROOT/'sim/ecg_pipeline500_host.c']
 exe=folder/'pipeline.exe';cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
 if not cc:raise RuntimeError('需要已有GCC，不安装')
 args=[cc,'-std=c11','-O2','-ffp-contract=off']+['-I'+str(ROOT/'src/ps'/n) for n in ('ecg_runtime','ecg_rate500','ecg_classification')]+list(map(str,sources))+['-lm','-o',str(exe)]
 result=subprocess.run(args,capture_output=True,env=dict(os.environ,TMP=str(folder),TEMP=str(folder)),timeout=90);(folder/'compile.log').write_bytes(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError('C参考编译失败')
 from scipy.signal import resample_poly
 cases={}
 for name,rec,seconds in [('record100','100',30),('record105','105',120),('synth240',None,120),('recovery',None,3)]:
  if rec:
   full,_,meta=load_record(raw,rec,'MLII');up=resample_poly(np.asarray(full,float),25,18);xs=np.clip(np.copysign(np.floor(abs(up)+.5),up),-32768,32767).astype('<i2')[:seconds*500]
  else:
   t=np.arange(seconds*500);period=125 if name=='synth240' else 500;xs=(20000*np.exp(-.5*((t%period-period/2)/5.)**2)-4000*np.exp(-.5*((t%period-period/2-13)/8.)**2)).astype('<i2');meta={'kind':'mathematical synthetic; no accuracy claim'}
  binary=folder/(name+'.bin');binary.write_bytes(xs.tobytes())
  source=folder/(name+'.csv')
  with source.open('x',newline='') as stream:
   w=csv.writer(stream);w.writerow(['index','sample','fs','scale']);w.writerows((i,int(x),500,4096) for i,x in enumerate(xs))
  native=subprocess.run([str(exe),'requests'],input=xs.tobytes(),capture_output=True,timeout=90)
  if native.returncode or len(native.stdout)%DT.itemsize:raise RuntimeError('C参考执行失败')
  requests=folder/(name+'.requests');requests.write_bytes(native.stdout);(folder/(name+'_host.log')).write_bytes(native.stderr)
  cases[name]=dict(samples=len(xs),binary=binary.name,csv=source.name,requests=requests.name,source=meta,hashes={q.name:digest(q) for q in (binary,source,requests)})
 info=dict(cases=cases,host_sha256=digest(exe),sources={q.relative_to(ROOT).as_posix():digest(q) for q in sources},scope='known360 resampled to source500; digital parity, not real500 acquisition or independent accuracy')
 (folder/'cases.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v['samples'] for k,v in cases.items()}))


def check_output(path,requests,trace):
 text=Path(path).read_text(encoding='ascii');events=[];windows={};states={}
 for line in text.splitlines():
  if line.startswith('E,'):
   f=line.split(',');events.append((int(f[1]),int(f[2]),int(f[3]),f[5]))
  m=re.fullmatch(r'L,I,WIN evt=(\d+) offset=(\d+)((?: [0-9A-F]{8}){8})',line)
  if m:
   key=(int(m[1]),int(m[2]))
   if key in windows:raise ValueError('窗口分块重复')
   windows[key]=[struct.unpack('<f',struct.pack('<I',int(v,16)))[0] for v in m[3].split()]
  m=re.fullmatch(r'L,I,CLASS evt=(\d+) state=(\d+) ready=(\d+)',line)
  if m:
   eid=int(m[1])
   if eid in states:raise ValueError('分类状态重复')
   states[eid]=(int(m[2]),int(m[3]))
 expected=[(int(r['beat_id']),int(r['position']),int(r['rr_samples']),'?') for r in requests]
 if events!=expected:raise ValueError('ARM事件/位置/RR/未知类别与C参考不符')
 max_error=0.;compared=0;expected_blocks=set()
 for r in requests:
  eid=int(r['beat_id']);status=int(r['input_status'])
  if states.get(eid)!=(status or 1,int(r['ready_at'])):raise ValueError('分类状态或实际就绪时刻不符')
  if trace and status!=4:
   values=[]
   for offset in range(0,128,8):expected_blocks.add((eid,offset));values.extend(windows[eid,offset])
   native=np.asarray(values,dtype=np.float32);np.testing.assert_allclose(native,r['waveform'],atol=1e-6,rtol=1e-6)
   max_error=max(max_error,float(abs(native-r['waveform']).max()));compared+=1
 if trace and set(windows)!=expected_blocks:raise ValueError('窗口块缺失或额外输出')
 if not trace and windows:raise ValueError('正常运行版意外启用窗口跟踪')
 return dict(events=len(events),windows_compared=compared,max_window_absolute_error=max_error,class_states=len(states))


def run(manifest,xsdb,cable,port,identity,fixtures,case,output,worker=False):
 m,files=resolve_runtime_artifacts(manifest,expected_rate=500);fixtures=Path(fixtures);spec=json.loads((fixtures/'cases.json').read_text())['cases'][case]
 for n,h in spec['hashes'].items():
  if digest(fixtures/n)!=h:raise ValueError('固定输入或参考SHA变化')
 xs=np.fromfile(fixtures/spec['binary'],dtype='<i2');requests=np.fromfile(fixtures/spec['requests'],dtype=DT)
 ports,_=enumerate_ports();device=validate_port(port,{'device_id':identity},ports)
 if not identity or not device['candidate']:raise ValueError('须核实USB实例')
 output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
 report=dict(passed=False,reason='failed',case=case,input=spec,build_id=m['build_id'],manifest=m,uart=device,window_trace=m['window_trace'],scope='physical Zynq ARM source500 digital parity; no real acquisition/wireless/final CNN/Flash')
 (output/'plan.json').write_text(json.dumps(report,indent=2)+'\n');serial=records=None
 try:
  args=[str(xsdb),str(ROOT/'board/classification_handoff/run.tcl'),cable,str(files['bit']),str(files['init']),str(files['elf'])]
  with (output/'jtag.log').open('xb') as log:p=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if p.returncode or 'ECG_CLASS_JTAG_STARTED' not in (output/'jtag.log').read_text(errors='replace'):raise RuntimeError('JTAG未完成，禁止发送')
  # 打开UART后只读等待本应用的就绪报文；旧启动原文完整保留，不向未知应用探测。
  serial=DuplexSerial(port);startup=bytearray();start=time.monotonic();ready=b'H,ECG-UART-1,ps-runtime500-ready,boot,UNKNOWN,QRS26-500-ARM,500,4096,0xD\n'
  while time.monotonic()-start<12:
   data=serial.read(4096);startup.extend(data)
   if ready in startup:break
   if len(startup)>65536:raise ValueError('启动输出超限')
   time.sleep(.001)
  else:raise TimeoutError('应用未输出500Hz就绪身份')
  (output/'startup_uart.bin').write_bytes(startup)
  serial.close();serial=None
  if worker:
   task=RuntimeWorker(fixtures/spec['csv'],port,output/'transfer',zynq_device=device,sampling_hz=500)
   task.start();task.join(len(xs)/500+40)
   if task.is_alive():task.stop();task.join(15);raise TimeoutError('后台未按时结束')
   info=task.snapshot()[0]
   if info['reason']!='completed' or info['error']:raise ValueError('后台失败：'+str(info))
   report.update(info);raw=output/'transfer/results/raw.log'
  else:
   records=BridgeRecords(output/'transfer');serial=DuplexSerial(port)
   client=BridgeClient(serial,records.monitor,uuid.uuid4().hex,'REPLAY',profile='runtime500',timeout=10,write_log=records.write)
   produced=0;origin=None;start=time.monotonic()
   while time.monotonic()-start<len(xs)/500+40:
    if client.started and client.waiting is None and origin is None:origin=time.monotonic()
    if origin is not None and not client.eof:
     due=min(len(xs),int((time.monotonic()-origin)*500)+1)
     if due>produced:
      values=[int(x) for x in xs[produced:due]];client.add(values)
      for index,x in enumerate(values,produced):records.row('normalized.csv',[index,x])
      produced=due
     if produced==len(xs):client.finish_source()
    client.pump()
    if client.done:break
    time.sleep(.001)
   if not client.done or client.lines:raise ValueError('缺少完整END/DONE或存在USB残行')
   report.update(client.summary());raw=output/'transfer/results/raw.log'
  report.update(check_output(raw,requests,m['window_trace']))
  if (report['confirmed'],report['echoed'])!=(len(xs),len(xs)):raise ValueError('样本确认/回传不完整')
  report.update(passed=True,reason='completed',samples=len(xs),raw_sha256=digest(raw))
 except Exception as exc:report.update(error=type(exc).__name__+': '+str(exc),reason='failed')
 finally:
  if serial is not None:
   try:serial.close()
   except Exception as exc:report.update(passed=False,reason='failed',error='关闭失败：'+str(exc))
  if records is not None:
   try:records.close(report)
   except Exception as exc:report.update(passed=False,reason='failed',error='保存失败：'+str(exc))
  (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k not in ('manifest','input','uart','timing')}),flush=True)
 if not report['passed']:raise RuntimeError('500Hz实板未通过，保留现场')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--raw',type=Path);p.add_argument('--output',type=Path,required=True)
 for n in ('manifest','xsdb','fixtures'):p.add_argument('--'+n,type=Path)
 for n in ('cable','port','device-id','case'):p.add_argument('--'+n)
 p.add_argument('--worker',action='store_true');a=p.parse_args()
 if a.prepare:prepare(a.output,a.raw)
 else:run(a.manifest,a.xsdb,a.cable,a.port,a.device_id,a.fixtures,a.case,a.output,a.worker)
