"""H27 CNN-BATCH-1送样与留证；500Hz单导联mV，四类N/S/V/F。"""
from pathlib import Path
import argparse,hashlib,json,math,secrets,struct,time,zlib
import numpy as np
from ecg_bridge_serial import DuplexSerial
from ecg_ports import enumerate_ports
from ecg_hgb import Channel as BaseChannel

MODEL='16d56a6b1065df35f3e11c4cc285055b421978bd451d5da1b72df8f1744fcfc7'
READY='H,CNN-BATCH-1,READY,500,mV,'+MODEL
PL_READY='H,CNN-PL-1,READY,500,mV,'+MODEL
DUAL_READY='H,ECG-DUAL-1,READY,500,mV,H27-FP32,HGB-Q40'
STREAM_READY='H,ECG-DUAL-STREAM-1,READY,500,mV,H27-FP32,HGB-Q40'
class Channel(BaseChannel):
    def wait_ready(self,timeout=10):
        deadline=time.monotonic()+timeout;headers=[(v+'\n').encode() for v in (READY,PL_READY,DUAL_READY,STREAM_READY)]
        while True:
            matches=[(self.buffer.index(h),h) for h in headers if h in self.buffer]
            if matches:
                at,header=min(matches,key=lambda x:x[0])
                if at+len(header)>8192:raise ValueError('启动同步超过8192字节')
                (self.directory/'startup_discard.bin').write_bytes(self.buffer[:at]);self.buffer=self.buffer[at+len(header):];return header.decode().strip()
            if len(self.buffer)>8192:raise ValueError('启动同步超过8192字节')
            if b'\n' in self.buffer and self.buffer.partition(b'\n')[0].startswith(b'H,'):raise ValueError('板端不是匹配的H27 CNN，未发送样本')
            block=self.serial.read()
            if block:self.rx.write(block);self.rx.flush();self.buffer.extend(block)
            elif time.monotonic()>deadline:raise TimeoutError('等待CNN身份超时，未发送样本')
            else:time.sleep(.002)
    def expect(self,expected):
        for _ in range(10):
            value=self.line()
            if value==expected:return
            if value in (READY,PL_READY,DUAL_READY,STREAM_READY):continue
            raise ValueError('板端响应不符合当前阶段：'+value)
        raise ValueError('没有收到当前阶段确认')

def parse_result(value,sid,total,previous):
    f=value.split(',')
    if len(f)!=11 or f[0]!='R':raise ValueError('CNN结果格式非法')
    session,beat,position,ready,status,cls=map(int,f[1:7])
    if session!=sid or beat!=len(previous)+1 or not 0<=position<=ready<total or (previous and (position<=previous[-1]['position'] or ready<previous[-1]['ready_at'])):raise ValueError('CNN会话/位置/序号不符')
    if any(len(v)!=8 for v in f[7:]):raise ValueError('CNN概率编码长度不符')
    p=[struct.unpack('>f',bytes.fromhex(v))[0] for v in f[7:]]
    if status==0:
        if cls not in range(4) or not all(math.isfinite(v) and 0<=v<=1 for v in p) or abs(sum(p)-1)>2e-6 or cls!=max(range(4),key=lambda i:p[i]):raise ValueError('CNN概率/类别非法')
    elif status not in (2,4) or cls!=-1 or not all(math.isnan(v) for v in p):raise ValueError('未分类状态非法')
    return dict(beat_id=beat,position=position,ready_at=ready,status=status,class_id=cls,label=('N','S','V','F')[cls] if cls>=0 else 'UNCLASSIFIED',probability=[v if math.isfinite(v) else None for v in p])

def parse_performance(value,sid):
    f=value.split(',')
    if len(f)!=10 or f[:3]!=['P',str(sid),'FP32']:raise ValueError('CNN性能报文身份错误')
    beats,mismatches,arm,call,core,hz,clock=map(int,f[3:])
    if min(beats,mismatches,arm,call,core)<0 or mismatches or hz<=0 or clock!=100000000:raise ValueError('CNN一致性或计时非法')
    if (not beats and any((arm,call,core))) or (beats and min(arm,call,core)<=0):raise ValueError('CNN拍数与计时不符')
    return dict(precision='FP32',scope='full_cnn_network',beats=beats,mismatches=mismatches,arm_ticks=arm,pl_call_ticks=call,pl_core_ticks=core,timer_hz=hz,pl_clock_hz=clock,
        arm_mean_us=arm/hz*1e6/beats if beats else None,pl_call_mean_us=call/hz*1e6/beats if beats else None,pl_core_mean_us=core/hz*1e6/beats if beats else None,
        call_speedup=arm/call if call else None,core_speedup=arm/core if core else None)

def transfer(signal,serial,directory,preprocess,sid=None,*,cancel=None,progress=None):
    signal=np.asarray(signal,np.float64)
    if signal.ndim!=1 or not 1<=len(signal)<=30000 or not np.isfinite(signal).all() or preprocess not in ('hp05','raw'):raise ValueError('仅接受1—30000点连续500Hz单导联mV及明确预处理')
    sid=sid or secrets.randbelow(0x7ffffffe)+1;channel=Channel(serial,directory)
    try:
        identity=channel.wait_ready();pl=identity in (PL_READY,DUAL_READY,STREAM_READY);performance=None
        channel.write(f'I,CNN-BATCH-1,{sid},500,mV,{preprocess},{len(signal)}\n'.encode());channel.expect(f'A,{sid},READY,32')
        for start in range(0,len(signal),32):
            if cancel is not None and cancel.is_set():
                channel.write(f'X,{sid}\n'.encode());channel.expect(f'S,{sid},CANCEL');raise InterruptedError('已取消CNN送样，不将部分记录分类')
            block=signal[start:start+32].astype('<f8',copy=False).tobytes()
            channel.write(f'B,{sid},{start},{len(block)//8},{zlib.crc32(block):08x}\n'.encode());channel.write(block);channel.expect(f'A,{sid},NEXT,{start+len(block)//8}')
            if progress:progress(start+len(block)//8,len(signal))
        channel.write(f'D,{sid},{len(signal)}\n'.encode());rows=[]
        while True:
            value=channel.line(timeout=120)
            if value.startswith('R,'):rows.append(parse_result(value,sid,len(signal),rows))
            elif value.startswith('P,'):
                if not pl or performance is not None:raise ValueError('意外或重复CNN性能报文')
                performance=parse_performance(value,sid)
            elif value.startswith('D,'):
                f=value.split(',')
                if len(f)!=8:raise ValueError('CNN完成报文长度不符')
                v=list(map(int,f[1:]))
                if v[:3]!=[sid,len(signal),len(rows)] or any(x<0 for x in v) or v[3]>len(signal):raise ValueError('CNN完成计数非法')
                if pl and (performance is None or performance['beats']!=sum(r['status']==0 for r in rows)):raise ValueError('CNN性能拍数与结果不符')
                result=dict(passed=True,session=sid,model_sha256=MODEL,classifier='CNN-H27-fold0',classes=['N','S','V','F'],f_meaning='fusion beat',execution_location='zynq_pl' if pl else 'zynq_arm',precision='FP32',sampling_hz=500,input_unit='mV',preprocess=preprocess,samples=len(signal),events=rows,clipped=v[3],compute_us=dict(input=v[4],prepare=v[5],classify=v[6]),performance=performance,model_qualified=False,flash_written=False)
                (Path(directory)/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return result
            else:raise ValueError('CNN分类阶段失败：'+value)
    finally:channel.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-mv',type=Path,required=True);p.add_argument('--port',required=True);p.add_argument('--device-id',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preprocess',choices=('hp05','raw'),required=True);a=p.parse_args()
    ports,_=enumerate_ports()
    if len([v for v in ports if v['port']==a.port and v['device_id']==a.device_id])!=1:raise ValueError('USB身份不匹配')
    signal=np.loadtxt(a.input_mv,delimiter=',');a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'input.json').write_text(json.dumps(dict(file=str(a.input_mv.resolve()),sha256=hashlib.sha256(a.input_mv.read_bytes()).hexdigest(),device_id=a.device_id,port=a.port),indent=2)+'\n')
    serial=DuplexSerial(a.port)
    try:
        r=transfer(signal,serial,a.output,a.preprocess);print(json.dumps(dict(passed=r['passed'],samples=r['samples'],events=len(r['events']),compute_us=r['compute_us'])))
    finally:serial.close()
if __name__=='__main__':main()
