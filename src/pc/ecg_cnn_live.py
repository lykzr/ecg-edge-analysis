"""实时采集/回放→有界队列→板上CNN；沿用原采集原文归档与账号隔离。"""
import csv,hashlib,json,queue,time
from collections import deque
from dataclasses import asdict
from pathlib import Path
from ecg_hgb_worker import HgbWorker
from ecg_capture_core import CaptureSample
from ecg_bridge_capture import NominalConverter
from ecg_cnn_stream import transfer_stream

class CnnLiveWorker(HgbWorker):
    def __init__(self,*args,**kwargs):
        kwargs['classifier']='cnn'
        # 父类仅限制整段蓝牙；流式自己校验并扩展采集上限。
        limit=kwargs.pop('sample_limit',5000)
        if type(limit) is not int or not 1<=limit<=1800000:raise ValueError('流式会话上限须1—1800000点')
        super().__init__(*args,sample_limit=min(limit,30000),**kwargs)
        self.limit=limit if self.kind=='bridge_serial' else 1800000
        if self.capture and self.kind=='bridge_serial':self.capture.sample_limit=limit
        self.queue=queue.Queue(maxsize=4096);self.arrivals=deque(maxlen=4096)
        self.info.update(protocol='CNN-STREAM-1',streaming=True,queue_limit=4096)
    def accept(self,sample,_value):
        value=NominalConverter.millivolts(sample.ecg_raw-8388608)
        with self.lock:
            index=self.info['source_samples']
            if sample.index!=index or index>=self.limit:raise ValueError('来源序号不连续或会话超限')
            self.samples.append(asdict(sample)|dict(ecg_nominal_mv=value))
            self.arrivals.append((index,time.perf_counter()))
            self.info['source_samples']=index+1
        try:self.queue.put(value,timeout=2 if self.kind=='bridge_csv' else 0)
        except queue.Full:raise ValueError('实时队列积压超过4096点；停止，不丢样续传')
    def publish(self,result):
        rows=[];previous=None;hz=(result['performance'] or {}).get('timer_hz')
        for e in result['events'][-256:]:
            rr=e['position']-previous if previous is not None else None
            # 使用完整事件前驱，避免显示环形窗口首拍RR丢失。
            i=e['beat_id']-1
            if i:rr=e['position']-result['events'][i-1]['position']
            previous=e['position'];row=dict(seq=e['beat_id'],pos=e['position'],index=e['position'],rr=rr,
                hr=30000/rr if rr else None,cls=e['label'],conf=max(e['probability']) if e['status']==0 else None,
                status=e['status'],probability=e['probability'],decision_at=e['ready_at'],
                algorithm_wait_ms=e['algorithm_wait_ms'],arm_class_id=e['arm_class_id'],pl_class_id=e['pl_class_id'])
            for name in ('arm','pl_call','pl_core','feature'):row[name+'_us']=e[name+'_ticks']/hz*1e6 if hz else None
            rows.append(row)
        last=rows[-1] if rows else None
        latest=next((e for e in reversed(result['events']) if e['status']==0),None)
        with self.lock:
            arrivals=dict(self.arrivals)
            for e in result['events']:
                if 'host_after_ready_ms' not in e and e['received_through'] in arrivals:
                    e['host_after_ready_ms']=max(0,(e['host_received_at']-arrivals[e['received_through']])*1000)
            for row,e in zip(rows,result['events'][-256:]):row['host_after_ready_ms']=e.get('host_after_ready_ms')
            self.info.update(confirmed=result['samples'],execution_location='zynq_pl',performance=result['performance'],
                precision='FP32',event_count=len(result['events']),queue_depth=self.queue.qsize(),
                class_counts={k:sum(e['label']==k for e in result['events']) for k in ('N','S','V','F','UNCLASSIFIED')},
                compute_us=result['compute_us'],clipped=result['clipped'])
            self.info['latest_performance']=dict(beat_id=latest['beat_id'],
                call_speedup=latest['arm_ticks']/latest['pl_call_ticks']) if latest else None
            self.view=dict(header=dict(firmware='cnn-stream-1',session=str(result['session']),source='ADC' if self.kind=='bridge_serial' else 'REPLAY',
                detector='CNN-H27-fold0-PL-FP32-STREAM',fs=500,scale=1,caps=20),
                samples=[dict(seq=s['index'],index=s['index'],raw=s['ecg_nominal_mv'],filt=None) for s in self.samples],
                events=rows,hr=last['hr'] if last else None,rr_ms=last['rr']*2 if last and last['rr'] else None,
                cls=last['cls'] if last else '未提供',waveform_origin='host_input')
    def blocks(self,writer):
        if self.capture:
            self.capture.start()
            while self.capture.is_alive() or not self.queue.empty():
                if self.cancel.is_set():self.capture.stop()
                block=[]
                while len(block)<32:
                    try:block.append(self.queue.get(timeout=.02))
                    except queue.Empty:break
                if block:
                    for v in block:writer.write(format(v,'.17g')+'\n')
                    yield block
            self.capture.join();ci,_=self.capture.snapshot()
            if ci['error']:raise ValueError('采集失败：'+ci['error'])
            if self.kind=='bridge_csv' and not ci.get('csv_complete') and not self.cancel.is_set():raise ValueError('CSV未完整读取')
        else:
            start=time.perf_counter();block=[]
            with Path(self.source).open(encoding='utf-8-sig',newline='') as stream, (self.directory/'input.csv').open('w',encoding='utf-8',newline='') as retained:
                reader=csv.reader(stream)
                header=next(reader)
                if header!=['index','sample','fs','scale']:raise ValueError('标准CSV格式不符')
                raw=csv.writer(retained);raw.writerow(header)
                for index,row in enumerate(reader):
                    if self.cancel.is_set():break
                    if index>=self.limit or len(row)!=4 or row[0]!=str(index) or row[2:]!=['500','4096']:raise ValueError('标准CSV序号/容量不符')
                    code=int(row[1])
                    if str(code)!=row[1] or not -32768<=code<=32767:raise ValueError('样本不是int16')
                    if self.realtime and self.cancel.wait(max(0,start+index/500-time.perf_counter())):break
                    value=code/4096
                    raw.writerow(row)
                    with self.lock:
                        self.samples.append(dict(asdict(CaptureSample(index,index/500,8388608,8388608+code)),ecg_nominal_mv=value))
                        self.arrivals.append((index,time.perf_counter()));self.info['source_samples']=index+1
                    writer.write(format(value,'.17g')+'\n');block.append(value)
                    if len(block)==32:yield block;block=[]
                if block:yield block
    def run(self):
        serial=None
        try:
            self.directory.mkdir(parents=True,exist_ok=False)
            self.info['state']='connecting';serial=self.factory(self.port,115200)
            self.started=time.perf_counter();self.info['state']='running'
            with (self.directory/'input_mv.csv').open('w',encoding='utf-8',newline='\n') as writer:
                result=transfer_stream(self.blocks(writer),serial,self.directory,self.mode,self.limit,
                    on_update=self.publish)
            self.publish(result)
            self.info.update(state='stopped',reason='stopped_by_user' if self.cancel.is_set() else 'completed',done=True,
                wall_seconds=result['wall_seconds'])
            (self.directory/'input.json').write_text(json.dumps(dict(samples=result['samples'],sampling_hz=500,unit='mV',preprocess=self.mode,
                sha256=hashlib.sha256((self.directory/'input_mv.csv').read_bytes()).hexdigest()),indent=2)+'\n',encoding='utf-8')
        except InterruptedError:self.info.update(state='stopped',reason='stopped_by_user')
        except Exception as exc:self.info.update(state='error',reason='failed',error=type(exc).__name__+': '+str(exc))
        finally:
            if self.capture and self.capture.is_alive():self.capture.stop();self.capture.join()
            if serial:
                try:serial.close()
                except Exception as exc:self.info.update(state='error',reason='failed',error='关闭板卡串口失败：'+str(exc))
            self.info['done']=True
            if self.directory.exists():(self.directory/'summary.json').write_text(json.dumps(self.info,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
