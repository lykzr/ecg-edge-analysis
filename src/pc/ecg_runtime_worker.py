"""360/500Hz已声明单位标准CSV的界面后台；不转换厂商500Hz，不在电脑执行检测。"""
from collections import deque
import csv,threading,time,uuid
from pathlib import Path
from ecg_bridge_core import BridgeClient
from ecg_bridge_records import BridgeRecords
from ecg_bridge_serial import DuplexSerial
from ecg_capture_core import CaptureSample
class RuntimeWorker(threading.Thread):
 def __init__(self,source,zynq_port,directory,*,zynq_device=None,port_factory=DuplexSerial,realtime=True,clock=time.monotonic,maximum=64*1024*1024,sampling_hz=360):
  if type(sampling_hz) is not int or sampling_hz not in (360,500):raise ValueError('标准输入仅支持360/500Hz')
  self.rate=sampling_hz;self.profile='runtime'+str(sampling_hz)
  if type(maximum) is not int or maximum<1024:raise ValueError('记录限额至少1024字节')
  self.maximum=maximum
  super().__init__(name='ecg-runtime-replay',daemon=False);self.source=Path(source);self.port=zynq_port;self.directory=Path(directory);self.device=dict(zynq_device or {})
  self.port_factory=port_factory;self.realtime=realtime;self.clock=clock;self.lock=threading.Lock();self.cancel=threading.Event();self.samples=deque(maxlen=4096);self.result=((),(),None)
  self.info=dict(state='starting',reason=None,error=None,source='REPLAY',sample_rate_hz=self.rate,profile=self.profile,source_status='标准CSV未打开',result_status='未连接',source_samples=0,confirmed=0,echoed=0,zynq_device=self.device,output_dir=str(directory),board_validated=False)
  self.capture=dict(total=0,clipped=0,error=None,reason=None)
 def stop(self):self.cancel.set()
 def snapshot(self):
  with self.lock:return dict(self.info),dict(self.capture),tuple(self.samples),self.result
 def run(self):
  records=None;port=None;client=None;reason='failed';error=None
  try:
   records=BridgeRecords(self.directory,maximum=self.maximum);port=self.port_factory(self.port)
   client=BridgeClient(port,records.monitor,uuid.uuid4().hex,'REPLAY',profile=self.profile,timeout=10,write_log=records.write,clock=self.clock)
   with self.source.open('rb') as source:
    def line():
     data=source.readline(4097)
     if len(data)>4096:raise ValueError('标准CSV单行超长')
     if data:records.write('input.csv',data)
     return data.decode('utf-8-sig')
    if next(csv.reader([line()]))!=['index','sample','fs','scale']:raise ValueError('标准CSV须index,sample,fs,scale，不是厂商RawData')
    index=0;origin=None;start=self.clock()
    while self.clock()-start<5100:
     if client.started and client.waiting is None and origin is None:origin=self.clock()
     if self.cancel.is_set() and not client.started:
      reason='stopped_by_user';break
     if self.cancel.is_set() and not client.eof:client.finish_source()
     if origin is not None and not client.eof:
      due=int((self.clock()-origin)*self.rate)+1 if self.realtime else index+32
      values=[];source_end=False
      for _ in range(min(32,max(0,due-index),client.capacity-len(client.queue))):
       text=line()
       if not text:
        if not index:raise ValueError('标准CSV无样本')
        source_end=True;break
       row=next(csv.reader([text]));
       if len(row)!=4 or row[0]!=str(index) or row[2:]!=[str(self.rate),'4096']:raise ValueError('标准CSV序号/单位/采样率不符')
       x=int(row[1])
       if str(x)!=row[1] or not -32768<=x<=32767:raise ValueError('标准CSV非规范int16')
       values.append(x);records.row('normalized.csv',[index,x])
       with self.lock:self.samples.append(CaptureSample(index,index/self.rate,8388608,8388608+x));self.capture['total']=index+1
       index+=1
      if values:client.add(values)
      if source_end:client.finish_source()
     client.pump()
     with self.lock:
      self.info.update(client.summary(),state='draining' if client.eof else 'running',source_status=f'标准CSV {self.rate}Hz/4096单位/mV',result_status='软件运行时结果')
      self.result=(tuple(records.monitor.samples),tuple(records.monitor.events),records.monitor.header)
     if client.done:reason='stopped_by_user' if self.cancel.is_set() else 'completed';break
     time.sleep(.001)
    else:raise TimeoutError('会话超过有界时长')
  except Exception as exc:error=type(exc).__name__+': '+str(exc)
  finally:
   if port is not None:
    try:port.close()
    except OSError as exc:error=error or str(exc)
   with self.lock:
    self.info.update(state='finished',reason=reason if error is None else 'failed',error=error);self.capture.update(reason=reason,error=error)
   if records is not None:
    try:records.close(dict(self.info))
    except OSError as exc:
     with self.lock:self.info.update(reason='failed',error='记录收尾失败：'+str(exc))
