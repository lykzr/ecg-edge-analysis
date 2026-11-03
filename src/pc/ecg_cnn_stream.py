"""CNN持续送样：分块背压、逐拍结果/同板ARM与PL计时；不在PC冒充模型。"""
import json,math,secrets,struct,time,zlib
from pathlib import Path
import numpy as np
from ecg_cnn import Channel,MODEL,STREAM_READY,TRIPLE_READY,parse_result,parse_performance,parse_quant_performance

MODEL_READY='H,CNN-STREAM-1,READY,500,mV,'+MODEL

def transfer_stream(blocks,serial,directory,preprocess,limit,*,cancel=None,on_update=None,sid=None,precision='FP32'):
    if preprocess not in ('hp05','raw') or not 1<=limit<=1800000:raise ValueError('流式输入合同错误')
    sid=sid or secrets.randbelow(0x7ffffffe)+1
    directory=Path(directory);channel=Channel(serial,directory);events=[];pending=None;performance=None;confirmed=0;comparison=None
    started=time.perf_counter();last_received=-1;finishing=False
    def result(final=False,compute=None,clipped=0):
        return dict(passed=final,session=sid,model_sha256=MODEL,classifier='CNN-H27-fold0',
            classes=['N','S','V','F'],execution_location='zynq_pl',precision=precision,streaming=True,quantization_comparison=comparison,
            sampling_hz=500,input_unit='mV',preprocess=preprocess,samples=confirmed,
            events=list(events),performance=performance,compute_us=compute or {},clipped=clipped,
            wall_seconds=time.perf_counter()-started,model_qualified=False,flash_written=False)
    def read_until(expected):
        nonlocal pending,performance,last_received,comparison
        while True:
            value=channel.line(timeout=15)
            if value==expected:
                if pending is not None:raise ValueError('计时没有对应分类结果')
                return
            if value.startswith('T,'):
                f=value.split(',')
                if len(f)!=10 or pending is not None:raise ValueError('逐拍计时重复或长度错误')
                ss,beat,received,arm,call,core,feature,ac,pc=map(int,f[1:])
                if ss!=sid or beat!=len(events)+1 or not last_received<=received<confirmed or min(arm,call,core,feature)<0 or core>call:raise ValueError('逐拍计时顺序/范围错误')
                if ac!=pc or ac not in (-1,0,1,2,3) or (ac>=0 and min(arm,call,core)<=0) or (ac<0 and any((arm,call,core))):raise ValueError('ARM/PL类别或计时不一致')
                last_received=received
                pending=dict(beat=beat,received_through=received,arm_ticks=arm,pl_call_ticks=call,pl_core_ticks=core,feature_ticks=feature,arm_class_id=ac,pl_class_id=pc)
            elif value.startswith('R,'):
                if pending is None:raise ValueError('缺少逐拍计时')
                row=parse_result(value,sid,confirmed,events)
                if row['class_id']!=pending['pl_class_id'] or pending['received_through']<row['ready_at']:raise ValueError('逐拍分类与计时不匹配')
                row.update(pending);pending=None
                row['algorithm_wait_ms']=(row['received_through']-row['position'])*2
                row['host_result_seconds']=time.perf_counter()-started
                row['host_received_at']=time.perf_counter()
                events.append(row)
            elif value.startswith('P,'):
                p=parse_performance(value,sid,precision)
                valid=sum(e['status']==0 for e in events)
                if p['beats']!=valid or any(p[k]!=sum(e[k] for e in events) for k in ('arm_ticks','pl_call_ticks','pl_core_ticks')):raise ValueError('逐拍与累计计时不符')
                performance=p
                if on_update:on_update(result())
            elif value.startswith('Q,'):
                q=parse_quant_performance(value,sid,performance)
                if comparison and (q['beats']<comparison['beats'] or any(q[k]<comparison[k] for k in ('class_changes','fp32_arm_ticks','fp32_pl_ticks','int8_arm_ticks','int8_pl_ticks'))):raise ValueError('量化累计计数倒退')
                comparison=q
                if on_update:on_update(result())
            elif value==MODEL_READY:continue
            elif value.startswith('D,'):
                if not finishing or pending is not None:raise ValueError('提前结束或逐拍计时缺结果')
                f=value.split(',')
                if len(f)!=8:raise ValueError('流式完成格式错误')
                v=list(map(int,f[1:]))
                if v[:3]!=[sid,confirmed,len(events)] or min(v)<0 or v[3]>confirmed or performance is None:raise ValueError('流式完成计数错误')
                if precision=='W8A8' and (comparison is None or comparison['beats']!=performance['beats']):raise ValueError('量化对比未完成')
                return result(True,dict(input=v[4],prepare=v[5],classify=v[6]),v[3])
            else:raise ValueError('流式响应异常：'+value)
    try:
        identity=channel.wait_ready()
        if precision not in ('FP32','W8A8') or identity not in (STREAM_READY,TRIPLE_READY) or (precision=='W8A8' and identity!=TRIPLE_READY):raise ValueError('板上不是匹配精度的CNN流式固件，未送样')
        protocol='CNN-INT8-STREAM-1' if precision=='W8A8' else 'CNN-STREAM-1'
        channel.write(f'I,{protocol},{sid},500,mV,{preprocess},{limit}\n'.encode())
        read_until(f'A,{sid},READY,32')
        for values in blocks:
            if cancel is not None and cancel.is_set():break
            values=np.asarray(values,np.float64)
            if values.ndim!=1 or not len(values) or not np.isfinite(values).all():raise ValueError('流式样本无效')
            for start in range(0,len(values),32):
                block=values[start:start+32].astype('<f8',copy=False).tobytes();count=len(block)//8
                if confirmed+count>limit:raise ValueError('超过会话上限，不截断冒充完整')
                channel.write(f'B,{sid},{confirmed},{count},{zlib.crc32(block):08x}\n'.encode());channel.write(block)
                confirmed+=count;read_until(f'A,{sid},NEXT,{confirmed}')
                if on_update:on_update(result())
        if not confirmed:raise InterruptedError('没有已确认样本')
        finishing=True
        channel.write(f'D,{sid},{confirmed}\n'.encode());final=read_until('never')
        if not isinstance(final,dict) or not final['passed']:raise ValueError('没有完成流式会话')
        if on_update:on_update(final)
        (directory/'result.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return final
    except BaseException:
        # 错误不续传、不补点；尝试取消，保留原始交互。
        try:channel.write(f'X,{sid}\n'.encode())
        except Exception:pass
        raise
    finally:channel.close()
