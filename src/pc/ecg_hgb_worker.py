"""网页板端整段分类后台：只做输入换算和显示，不在PC执行模型。"""
from collections import deque
from dataclasses import asdict
from pathlib import Path
import csv,hashlib,json,threading,time
import numpy as np
from ecg_hgb import transfer,MODEL
from ecg_bridge_serial import DuplexSerial
from ecg_capture_core import CaptureWorker,CaptureSample
from ecg_bridge_capture import NominalConverter


class HgbWorker(threading.Thread):
    def __init__(self,kind,source,port,directory,*,preprocess=None,sample_limit=5000,
                 realtime=True,zynq_device=None,source_device=None,port_factory=DuplexSerial,classifier='hgb'):
        super().__init__(name='ecg-hgb-arm',daemon=False)
        if kind not in ('standard500','bridge_csv','bridge_serial'):raise ValueError('板端模型只接标准500Hz或厂商500Hz')
        if kind=='standard500' and preprocess not in ('hp05','raw'):raise ValueError('必须声明标准500Hz的hp05/raw状态')
        if kind=='bridge_serial' and not 1<=sample_limit<=30000:raise ValueError('板端整段模型采集上限须为1—30000点')
        self.kind,self.source,self.port,self.directory=kind,source,port,Path(directory)
        if classifier not in ('hgb','cnn'):raise ValueError('板端分类器必须为hgb或cnn')
        self.classifier=classifier
        if classifier=='cnn':
            from ecg_cnn import MODEL as selected_model
        else:selected_model=MODEL
        self.mode=preprocess if kind=='standard500' else 'hp05'
        self.realtime,self.factory=realtime,port_factory
        self.cancel=threading.Event();self.lock=threading.RLock()
        self.samples=deque(maxlen=4096);self.values=[];self.capture=None
        self.info=dict(state='starting',reason=None,error=None,source_samples=0,confirmed=0,done=False,
                       execution_location='pending_board_identity',model_sha256=selected_model,qualified=False,classifier=classifier,
                       protocol='CNN-BATCH-1' if classifier=='cnn' else 'HGB-BATCH-1',sampling_hz=500,preprocess=self.mode,
                       zynq_device=zynq_device,source_device=source_device,upstream_source_drop=None)
        self.view=dict(header=None,samples=[],events=[],hr=None,rr_ms=None,cls='未提供',waveform_origin='host_input')
        self.capture_info={}
        if kind!='standard500':
            self.capture=CaptureWorker('serial' if kind=='bridge_serial' else 'csv',source,self.directory/'capture',
                on_sample=self.accept,sample_limit=sample_limit if kind=='bridge_serial' else None,
                realtime=realtime,device_info=source_device,normalization='nominal500')
    def accept(self,sample,_value):
        with self.lock:
            if sample.index!=len(self.values) or len(self.values)>=30000:raise ValueError('板端模型序列不连续或超过30000点；未截断推理')
            # 保留完整未额外滤波的CH2标称mV；不使用显示滤波或conditioned列。
            self.values.append(NominalConverter.millivolts(sample.ecg_raw-8388608))
            self.samples.append(asdict(sample)|dict(ecg_nominal_mv=self.values[-1]))
            self.info['source_samples']=len(self.values)
    def stop(self):
        self.cancel.set()
        if self.capture:self.capture.stop()
    def snapshot(self):
        with self.lock:
            ci,_=self.capture.snapshot() if self.capture else (self.capture_info,())
            return dict(self.info),dict(ci),tuple(self.samples),dict(self.view)
    def run(self):
        serial=None
        try:
            self.directory.mkdir(parents=True,exist_ok=False)
            self.info['state']='running'
            if self.capture:
                self.capture.start()
                while self.capture.is_alive():
                    self.capture.join(.1)
                    if self.cancel.is_set():self.capture.stop()
                ci,_=self.capture.snapshot()
                if ci['error']:raise ValueError('来源失败：'+ci['error'])
                if self.kind=='bridge_csv' and not ci.get('csv_complete'):raise ValueError('厂商CSV未完整读取')
            else:
                started=time.monotonic()
                with Path(self.source).open(encoding='utf-8-sig',newline='') as stream, (self.directory/'input.csv').open('w',encoding='utf-8',newline='') as raw:
                    reader=csv.reader(stream);writer=csv.writer(raw)
                    head=next(reader);writer.writerow(head)
                    if head!=['index','sample','fs','scale']:raise ValueError('标准CSV须index,sample,fs,scale')
                    for row in reader:
                        if self.cancel.is_set():break
                        index=len(self.values)
                        if index>=30000 or len(row)!=4 or row[0]!=str(index) or row[2:]!=['500','4096']:raise ValueError('标准CSV序号/采样率/比例/容量不符')
                        value=int(row[1])
                        if str(value)!=row[1] or not -32768<=value<=32767:raise ValueError('标准样本须规范int16')
                        writer.writerow(row)
                        if self.realtime and self.cancel.wait(max(0,started+index/500-time.monotonic())):break
                        with self.lock:
                            self.values.append(value/4096)
                            self.samples.append(asdict(CaptureSample(index,index/500,8388608,8388608+value)))
                            self.info['source_samples']=len(self.values)
                self.capture_info=dict(total=len(self.values))
            if self.cancel.is_set():raise InterruptedError('已停止并保存来源，未提交不完整分类')
            if not self.values:raise ValueError('没有可送板样本')
            np.savetxt(self.directory/'input_mv.csv',self.values,delimiter=',',fmt='%.17g')
            (self.directory/'input.json').write_text(json.dumps(dict(
                sha256=hashlib.sha256((self.directory/'input_mv.csv').read_bytes()).hexdigest(),
                samples=len(self.values),sampling_hz=500,unit='mV',preprocess=self.mode,
                zynq_device=self.info['zynq_device'],source_device=self.info['source_device']),
                ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            self.info['state']='draining'
            serial=self.factory(self.port,115200)
            def progress(n,total):
                with self.lock:self.info.update(confirmed=n,total=total)
            selected_transfer=transfer
            if self.classifier=='cnn':
                from ecg_cnn import transfer as selected_transfer
            result=selected_transfer(self.values,serial,self.directory,self.mode,cancel=self.cancel,progress=progress)
            rows=[];previous=None
            for event in result['events']:
                rr=event['position']-previous if previous is not None else 0
                previous=event['position']
                rows.append(dict(seq=event['beat_id'],pos=event['position'],index=event['position'],rr=rr or None,
                    hr=30000/rr if rr else None,cls=event['label'],conf=max(event['probability']) if event['status']==0 else None,
                    status=event['status'],probability=event['probability'],decision_at=event.get('decision_at',event['ready_at'])))
            last=rows[-1] if rows else None
            with self.lock:
                self.view=dict(header=dict(firmware='cnn-batch-1' if self.classifier=='cnn' else 'hgb-batch-1',session=str(result['session']),source='REPLAY' if self.kind!='bridge_serial' else 'ADC',
                    detector=('CNN-H27-fold0-' if self.classifier=='cnn' else 'HGB-v92-fold0-')+('PL-'+result['precision'] if result['execution_location']=='zynq_pl' else 'ARM'),fs=500,scale=1,caps=20),
                    samples=[dict(seq=i,index=i,raw=self.values[i],filt=None) for i in range(max(0,len(self.values)-4096),len(self.values))],
                    events=rows[-256:],hr=last['hr'] if last else None,rr_ms=last['rr']*2 if last and last['rr'] else None,
                    cls=last['cls'] if last else '未提供',waveform_origin='host_input')
                self.info.update(state='stopped',reason='completed',done=True,compute_us=result['compute_us'],clipped=result['clipped'],
                    execution_location=result['execution_location'],performance=result['performance'],precision=result['precision'],
                    event_count=len(result['events']),class_counts={label:sum(e['label']==label for e in result['events']) for label in (('N','S','V','F','UNCLASSIFIED') if self.classifier=='cnn' else ('N','S','VF','UNCLASSIFIED'))})
        except InterruptedError as exc:self.info.update(state='stopped',reason='stopped_by_user',error=None,note=str(exc))
        except Exception as exc:self.info.update(state='error',reason='failed',error=type(exc).__name__+': '+str(exc))
        finally:
            if self.capture and self.capture.is_alive():self.capture.stop();self.capture.join()
            if serial:
                try:serial.close()
                except Exception as exc:self.info.update(state='error',reason='failed',error=str(exc))
            try:
                (self.directory/'summary.json').write_text(json.dumps(self.info,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
            except Exception as exc:self.info.update(state='error',reason='failed',error='摘要保存失败：'+str(exc))
