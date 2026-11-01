"""独立HGB-BATCH-1电脑送样入口；输入500Hz单导联mV，不代替网页或厂商解码。"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import secrets
import struct
import time
import zlib
import numpy as np
from ecg_bridge_serial import DuplexSerial
from ecg_ports import enumerate_ports

MODEL='375cf45ac1f315ecc517a219cb03340727304db8e7738626ac4b4920a5af00f8'
READY='H,HGB-BATCH-1,READY,500,mV,'+MODEL
PL_READY='H,HGB-PL-1,READY,500,mV,'+MODEL
LEGACY_READY='H,ECG-UART-1,ps-runtime500-ready,boot,UNKNOWN,QRS26-500-ARM,500,4096,0xD'

class Channel:
    def __init__(self,serial,directory):
        self.serial=serial;self.buffer=bytearray();self.directory=Path(directory)
        self.tx=(self.directory/'tx.bin').open('wb');self.rx=(self.directory/'rx.log').open('wb')
    def close(self):self.tx.close();self.rx.close()
    def write(self,data):
        deadline=time.monotonic()+10
        while data:
            n=self.serial.write(data[:256])
            if n:self.tx.write(data[:n]);self.tx.flush();data=data[n:]
            elif time.monotonic()>deadline:raise TimeoutError('发送超时')
            else:time.sleep(.001)
    def wait_ready(self,timeout=10):
        """仅握手前允许有界启动同步；原始字节留证，活动会话不跳过错误。"""
        deadline=time.monotonic()+timeout
        headers=[(value+'\n').encode() for value in (READY,PL_READY,LEGACY_READY)]
        while True:
            matches=[(self.buffer.find(header),header) for header in headers if header in self.buffer]
            if matches:
                offset,header=min(matches,key=lambda item:item[0])
                if offset+len(header)>8192:raise ValueError('启动同步超过8192字节，未发送任何样本')
                (self.directory/'startup_discard.bin').write_bytes(self.buffer[:offset])
                self.buffer=self.buffer[offset+len(header):]
                return header.decode().strip()
            if len(self.buffer)>8192:raise ValueError('启动同步超过8192字节，未发送任何样本')
            if b'\n' in self.buffer:
                first=self.buffer.partition(b'\n')[0]
                if first.startswith(b'H,'):raise ValueError('板卡就绪身份不匹配，未发送任何样本')
            block=self.serial.read()
            if block:self.rx.write(block);self.rx.flush();self.buffer.extend(block)
            elif time.monotonic()>deadline:raise TimeoutError('启动同步超时，未发送任何样本')
            else:time.sleep(.002)
    def line(self,timeout=20):
        deadline=time.monotonic()+timeout
        while True:
            if b'\n' in self.buffer:
                raw,_,tail=self.buffer.partition(b'\n');self.buffer=bytearray(tail)
                if len(raw)>255:raise ValueError('板端行超长')
                return raw.decode('ascii').rstrip('\r')
            if len(self.buffer)>8192:raise ValueError('接收缓存超限')
            block=self.serial.read()
            if block:self.rx.write(block);self.rx.flush();self.buffer.extend(block)
            elif time.monotonic()>deadline:raise TimeoutError('等待HGB板端报文超时')
            else:time.sleep(.002)
    def expect(self,expected):
        for _ in range(10):
            value=self.line()
            if value==expected:return
            if value in (READY,PL_READY,LEGACY_READY):continue
            raise ValueError('板端响应不符合当前阶段：'+value)
        raise ValueError('没有收到当前阶段确认')

def parse_result(value,sid,total,previous):
    f=value.split(',')
    if len(f)!=11 or f[0]!='R':raise ValueError('非法分类结果')
    integers=[int(x) for x in f[1:8]]
    session,beat,position,ready,decision,status,cls=integers
    if session!=sid or beat!=len(previous)+1 or not 0<=position<=ready<=decision<total or (previous and position<=previous[-1]['position']):raise ValueError('结果序号/位置不连续')
    p=[struct.unpack('>d',bytes.fromhex(x))[0] for x in f[8:11]]
    if status==0:
        if cls not in (0,1,2) or not all(math.isfinite(v) and 0<=v<=1 for v in p) or abs(sum(p)-1)>1e-10 or cls!=max(range(3),key=lambda i:p[i]):raise ValueError('有效分类概率或类别非法')
    elif status not in (2,4) or cls!=-1 or not all(math.isnan(v) for v in p):raise ValueError('未知状态被错误分类')
    return dict(beat_id=beat,position=position,ready_at=ready,decision_at=decision,status=status,class_id=cls,label=('N','S','VF')[cls] if cls>=0 else 'UNCLASSIFIED',probability=[v if math.isfinite(v) else None for v in p])

def parse_performance(value,sid):
    f=value.split(',')
    if len(f)!=10 or f[:3]!=['P',str(sid),'Q40']:raise ValueError('PL性能报文身份错误')
    beats,mismatches,arm,call,cycles,hz,clock=map(int,f[3:])
    if min(beats,mismatches,arm,call,cycles)<0 or hz<=0 or clock!=100000000 or mismatches:
        raise ValueError('PL性能计数或ARM/PL一致性错误')
    if (beats==0 and any((arm,call,cycles))) or (beats>0 and min(arm,call,cycles)<=0):raise ValueError('PL心拍与计时不符')
    return dict(precision='Q40',beats=beats,mismatches=mismatches,arm_ticks=arm,pl_call_ticks=call,
        pl_core_cycles=cycles,timer_hz=hz,pl_clock_hz=clock,
        arm_mean_us=arm/hz*1e6/beats if beats else None,
        pl_call_mean_us=call/hz*1e6/beats if beats else None,
        pl_core_mean_us=cycles/clock*1e6/beats if beats else None,
        call_speedup=arm/call if call else None,core_speedup=(arm/hz)/(cycles/clock) if cycles else None)


def transfer(signal,serial,directory,preprocess,sid=None,*,cancel=None,progress=None):
    signal=np.asarray(signal,dtype=np.float64)
    if signal.ndim!=1 or not 1<=len(signal)<=30000 or not np.isfinite(signal).all() or preprocess not in ('hp05','raw'):raise ValueError('仅接1—30000点有限单导联mV及明确hp05/raw')
    sid=sid or secrets.randbelow(0x7ffffffe)+1
    channel=Channel(serial,directory)
    try:
        identity=channel.wait_ready();pl=identity==PL_READY;performance=None
        channel.write(f'I,HGB-BATCH-1,{sid},500,mV,{preprocess},{len(signal)}\n'.encode())
        channel.expect(f'A,{sid},READY,32')
        for start in range(0,len(signal),32):
            if cancel is not None and cancel.is_set():
                channel.write(f'X,{sid}\n'.encode());channel.expect(f'S,{sid},CANCEL')
                raise InterruptedError('用户取消板端分类送样，未把部分数据当成完整结果')
            block=signal[start:start+32].astype('<f8',copy=False).tobytes()
            channel.write(f'B,{sid},{start},{len(block)//8},{zlib.crc32(block):08x}\n'.encode())
            channel.write(block);channel.expect(f'A,{sid},NEXT,{start+len(block)//8}')
            if progress:progress(start+len(block)//8,len(signal))
        channel.write(f'D,{sid},{len(signal)}\n'.encode());rows=[]
        while True:
            value=channel.line()
            if value.startswith('R,'):rows.append(parse_result(value,sid,len(signal),rows))
            elif value.startswith('P,'):
                if not pl or performance is not None:raise ValueError('意外或重复PL性能报文')
                performance=parse_performance(value,sid)
            elif value.startswith('D,'):
                fields=value.split(',')
                if len(fields)!=8:raise ValueError('完成报文长度错误')
                values=[int(v) for v in fields[1:]]
                if values[:3]!=[sid,len(signal),len(rows)] or any(v<0 for v in values):raise ValueError('完成计数错误')
                result=dict(passed=True,session=sid,model_sha256=MODEL,model_qualified=False,classes=['N','S','VF'],vf_meaning='V/E/F merged, not ventricular fibrillation',sampling_hz=500,input_unit='mV',preprocess=preprocess,samples=len(signal),events=rows,clipped=values[3],compute_us=dict(input=values[4],prepare=values[5],classify=values[6]),flash_written=False)
                if pl and (performance is None or performance['beats']!=sum(r['status']==0 for r in rows)):
                    raise ValueError('PL性能心拍数与有效分类数不符')
                result.update(execution_location='zynq_pl' if pl else 'zynq_arm',performance=performance,
                    precision='Q40' if pl else 'float64',classifier='HGB-v92-fold0')
                break
            else:raise ValueError('分类阶段失败：'+value)
        (Path(directory)/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result
    finally:channel.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-mv',type=Path,required=True);p.add_argument('--port',required=True);p.add_argument('--device-id',required=True)
    p.add_argument('--preprocess',choices=('hp05','raw'),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    ports,_=enumerate_ports()
    if len([v for v in ports if v['port']==a.port and v['device_id']==a.device_id])!=1:raise ValueError('USB身份不匹配')
    signal=np.loadtxt(a.input_mv,delimiter=',');a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'input.json').write_text(json.dumps(dict(file=str(a.input_mv.resolve()),sha256=hashlib.sha256(a.input_mv.read_bytes()).hexdigest(),device_id=a.device_id,port=a.port,scope='explicit 500Hz single-channel mV; no vendor decoding'),indent=2)+'\n')
    serial=DuplexSerial(a.port)
    try:
        result=transfer(signal,serial,a.output,a.preprocess)
        print(json.dumps(dict(passed=result['passed'],samples=result['samples'],events=len(result['events']),compute_us=result['compute_us'])))
    finally:serial.close()
if __name__=='__main__':main()
