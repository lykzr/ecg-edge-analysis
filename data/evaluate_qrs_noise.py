"""冻结研究26的官方NST压力评估；全段计分，不改算法、不安装或下载。"""
import argparse
from collections import Counter
import inspect
import json
from pathlib import Path
import sys
import time
import statistics
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/reference'))
from ecg_dataset import BEAT_CODES, digest, load_record, metrics, write_csv, decode212, annotations
from ecg_input import map_adc


def region(index, fs=360):
    """官方默认：首5分钟无添加噪声，此后2分钟交替；不是信号质量标签。"""
    if index < 300*fs:
        return 'startup_clean'
    return 'noise_on' if ((index-300*fs)//(120*fs)) % 2 == 0 else 'noise_off'


def decode_channels(blob, fmt, count):
    if fmt=='212':
        channels=decode212(blob)
    elif fmt=='16':
        if len(blob)!=count*4:
            raise ValueError('16位双通道实际字节数不符')
        pairs=list(struct.iter_unpack('<hh',blob))
        channels=[[p[i] for p in pairs] for i in range(2)]
    else:
        raise ValueError('不支持的NST数据编码：'+fmt)
    if any(len(c)!=count for c in channels):
        raise ValueError('实际波形长度不符')
    return channels


def load_noise_record(raw,name,mapping):
    """NST同时有212和16编码；核对WFDB完整数字解码，不改原MIT读取器。"""
    import wfdb
    lines=(raw/(name+'.hea')).read_text().splitlines()
    head=lines[0].split()
    if head[:3]!=[name,'2','360'] or int(head[3])!=650000:
        raise ValueError('NST头信息不符合冻结样本数/采样率')
    fields=[line.split() for line in lines[1:3]]
    fmt=fields[0][1]
    if any(f[0]!=name+'.dat' or f[1]!=fmt for f in fields):
        raise ValueError('通道文件或格式不一致')
    count=int(head[3]);channels=decode_channels((raw/(name+'.dat')).read_bytes(),fmt,count)
    oracle=wfdb.rdrecord(str(raw/name),physical=False).d_signal
    for i,(channel,f) in enumerate(zip(channels,fields)):
        checksum=(sum(channel)+32768)%65536-32768
        if channel[0]!=int(f[5]) or checksum!=int(f[6]) or channel!=oracle[:,i].tolist():
            raise ValueError('NST解码首值/校验和/WFDB对照不符')
    selected=next(i for i,f in enumerate(fields) if f[-1]=='MLII')
    f=fields[selected]
    match=re.fullmatch(r'(\d+)(?:\((-?\d+)\))?(?:/mV)?',f[2])
    if not match:raise ValueError('未知gain/baseline单位')
    baseline=int(match[2]) if match[2] is not None else int(f[4])
    applied=baseline if mapping=='header' else int(f[4])
    samples,clipped=map_adc(channels[selected],applied,int(match[1]))
    payload=(raw/(name+'.atr')).read_bytes()
    if len(payload)%2 or payload[-2:]!=b'\0\0':raise ValueError('标注EOF不完整')
    labels=annotations(payload)
    if [i for i,_ in labels]!=sorted(i for i,_ in labels) or any(not 0<=i<count for i,_ in labels):
        raise ValueError('标注乱序或越界')
    return samples,labels,dict(source_sha256={name+'.'+ext:digest(raw/(name+'.'+ext)) for ext in ('hea','dat','atr')},
        samples=count,baseline=baseline,mapping_baseline=applied,adc_per_mv=int(match[1]),
        input_clipped=clipped,format=fmt,wfdb_digital_decode_verified=True)


def score(labels, positions, count, tolerance, gate):
    if positions != sorted(set(positions)) or any(type(i) is not int or not 0 <= i < count for i in positions):
        raise ValueError('检测位置必须是严格递增的界内整数')
    beats = [(i,c) for i,c in labels if c in BEAT_CODES]
    refs = [i for i,_ in beats]
    if any(not 0 <= i < count for i in refs):
        raise ValueError('心搏标注越界')
    m,pairs,missed,extra = metrics(refs, positions, tolerance)
    counts = Counter(c for _,c in beats)
    matched = Counter(beats[i][1] for i,_,_ in pairs)
    m.update(v_reference=counts[5], v_matched=matched[5],
             v_recall=matched[5]/counts[5] if counts[5] else None,
             beat_types={str(c):dict(reference=n,matched=matched[c]) for c,n in counts.items()})
    checks = {k:(m[k] is not None and m[k]>=gate[k]) for k in ('sensitivity','positive_predictivity')}
    checks.update({k:(m[k] is not None and m[k]<=gate[k]) for k in ('position_mae_ms','rr_mae_ms')})
    checks['v_recall'] = m['v_recall'] is None or m['v_recall'] >= gate['v_recall']
    # 全局匹配一次后归属时间段，避免边界重新匹配改变分母。
    def segment(start, end):
        selected=[(i,j,d) for i,j,d in pairs if start<=refs[i]<end]
        vc=sum(c==5 and start<=p<end for p,c in beats)
        vm=sum(beats[i][1]==5 for i,_,_ in selected)
        tp=len(selected);fn=sum(start<=i<end for i in missed);fp=sum(start<=i<end for i in extra)
        rr_errors=[((positions[d]-positions[b])-(refs[c]-refs[a]))*1000/360
                   for (a,b,_),(c,d,_) in zip(pairs,pairs[1:])
                   if c==a+1 and d==b+1 and start<=refs[a]<end and start<=refs[c]<end]
        return dict(start=start,end=end,TP=tp,FN=fn,FP=fp,
                    sensitivity=tp/(tp+fn) if tp+fn else None,
                    positive_predictivity=tp/(tp+fp) if tp+fp else None,
                    v_reference=vc,v_matched=vm,v_recall=vm/vc if vc else None,
                    position_mae_ms=sum(abs(d)*1000/360 for _,_,d in selected)/tp if tp else None,
                    rr_mae_ms=statistics.mean(map(abs,rr_errors)) if rr_errors else None,
                    matched_rr_intervals=len(rr_errors))
    blocks=[]
    start=0
    while start<count:
        end=min(300*360 if start==0 else start+120*360,count)
        blocks.append(dict(phase=region(start),**segment(start,end)))
        start=end
    m.update(checks=checks,provisional_gate='PASS' if all(checks.values()) else 'FAIL',time_blocks=blocks)
    return m,pairs,missed,extra,refs


def run(raw, output, protocol_path, selected=None, mapping='header'):
    from qrs_research import replay
    raw=raw.resolve();output=output.resolve()
    output.relative_to(ROOT/'tmp')
    if output.exists():
        raise FileExistsError('输出已存在，不覆盖')
    protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
    if mapping not in protocol['input_mappings']:
        raise ValueError('未冻结的输入映射')
    frozen=json.loads((ROOT/'data/qrs_research_protocol.json').read_text(encoding='utf-8'))
    if protocol['source_protocol_sha256'] != digest(ROOT/'data/qrs_research_protocol.json'):
        raise ValueError('算法协议发生变化')
    for name,sha in frozen['frozen_sha256'].items():
        if digest(ROOT/name)!=sha:
            raise ValueError('冻结源码发生变化：'+name)
    for name,sha in protocol['runner_sha256'].items():
        if digest(ROOT/name)!=sha:
            raise ValueError('计分入口发生变化：'+name)
    import numpy, scipy, wfdb
    from wfdb.processing.qrs import GQRS
    if wfdb.__version__!=frozen['wfdb_version'] or digest(Path(inspect.getfile(GQRS)))!=frozen['wfdb_source_sha256']:
        raise ValueError('WFDB来源与冻结协议不符')
    # 下载清单来自官方NST和MIT各自校验；不覆盖官方原文。
    checks={}
    for name in ('SHA256SUMS.txt','MITDB_SHA256SUMS.txt'):
        for line in (raw/name).read_text().splitlines():
            f=line.split()
            if len(f)==2: checks[f[1].lstrip('*')]=f[0]
    expected=json.loads((raw/'verified_checksums.json').read_text())
    for item in expected:
        if digest(raw/item['name'])!=item['sha256'] or checks.get(item['name'])!=item['sha256']:
            raise ValueError('原始数据SHA不符：'+item['name'])
    required={r['record']+'.'+ext for r in protocol['records'] for ext in ('hea','dat','atr')}
    if required != {row['name'] for row in expected}:
        raise ValueError('数据清单与协议的42文件不一致')
    output.mkdir(parents=True)
    # 兼容共享解码器的单目录索引；官方清单不改，数据只读。
    proxy=output/'verified_input';proxy.mkdir()
    import shutil
    for name in sorted(required):
        shutil.copy2(raw/name,proxy/name)
    (proxy/'SHA256SUMS.txt').write_text(''.join(checks[n]+'  '+n+'\n' for n in sorted(required)))
    records=protocol['records']
    if selected:
        if not set(selected)<=set(r['record'] for r in records):raise ValueError('协议外记录')
        records=[r for r in records if r['record'] in selected]
    report=dict(protocol=protocol,protocol_sha256=digest(protocol_path),
                environment=dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,wfdb=wfdb.__version__),
                mapping=mapping,scope='known-patient official noise stress; offline research26, not independent/PS/PL/board',rows=[])
    (output/'protocol.json').write_bytes(protocol_path.read_bytes())
    clean={}
    nst_references={}
    for b in ('118','119'):
        samples,labels,meta=load_record(proxy,b,'MLII');clean[b]=(samples,labels,meta)
        reference=annotations((proxy/(b+'e24.atr')).read_bytes())
        if len(labels)!=len(reference) or [c for _,c in labels]!=[c for _,c in reference]:
            raise ValueError('两个官方标注的数量/类型顺序冲突')
        for suffix in ('e18','e12','e06','e00','e_6'):
            if annotations((proxy/(b+suffix+'.atr')).read_bytes())!=reference:
                raise ValueError('同一基础记录的NST参考标注不一致')
        nst_references[b]=reference
    for item in records:
        name=item['record'];start=time.perf_counter()
        if name in ('118','119'):
            samples,labels,meta=load_record(proxy,name,'MLII')
        else:
            samples,labels,meta=load_noise_record(proxy,name,mapping)
        clean_samples,clean_labels,_=clean[item['base_record']]
        nst_labels=nst_references[item['base_record']]
        if len(samples)!=len(clean_samples) or (name not in ('118','119') and labels!=nst_labels):
            raise ValueError('干净/噪声记录长度或NST配对标注不一致：'+name)
        # 不通过拟合偏置/增益或标注校正对齐；两种映射分别完整计分。
        prefix=[a-b for a,b in zip(samples[:108000],clean_samples[:108000])]
        pair_check=dict(same_annotations=True,same_length=True,
                        clean_prefix_difference_min=min(prefix),clean_prefix_difference_max=max(prefix),
                        mapping=mapping,primary_reference='NST annotations for clean and noisy',
                        mit_nst_annotations_identical=clean_labels==nst_labels)
        if mapping=='adc_zero' and (min(prefix)!=0 or max(prefix)!=0):
            raise ValueError('ADCzero诊断臂的未加噪前缀不相等：'+name)
        positions,events,details=replay(samples,frozen['candidate_config'])
        m,pairs,missed,extra,refs=score(nst_labels,positions,len(samples),protocol['tolerance_samples'],protocol['gate'])
        secondary,*_=score(clean_labels,positions,len(samples),protocol['tolerance_samples'],protocol['gate'])
        folder=output/name;folder.mkdir()
        write_csv(folder/'positions.csv',['index'],((i,) for i in positions))
        write_csv(folder/'events.csv',['emission_index','index','rr_samples'],events)
        write_csv(folder/'matches.csv',['reference_index','detected_index','error_samples'],((refs[i],positions[j],d) for i,j,d in pairs))
        write_csv(folder/'missed.csv',['index'],((i,) for i in missed))
        write_csv(folder/'extra.csv',['index'],((i,) for i in extra))
        row=dict(**item,**meta,**m,pair_check=pair_check,details=details,elapsed_seconds=time.perf_counter()-start)
        row['mit_annotation_score']=secondary
        row['reference_sha256']=dict(primary_nst=digest(proxy/(item['base_record']+'e24.atr')),
                                    secondary_mit=digest(proxy/(item['base_record']+'.atr')))
        delays=[(emitted-index)*1000/360 for emitted,index,_ in events]
        row['sample_confirmation_delay_ms']=dict(mean=statistics.mean(delays),minimum=min(delays),maximum=max(delays)) if delays else None
        (folder/'summary.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        report['rows'].append(row)
        (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(name,{k:row[k] for k in ('TP','FN','FP','v_recall','position_mae_ms','provisional_gate')},flush=True)
    print('DONE',len(report['rows']),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--protocol',type=Path,default=ROOT/'data/qrs_noise_protocol.json')
    p.add_argument('--records',nargs='+',help='协议内预检子集；不能当完整压力集')
    p.add_argument('--mapping',choices=['header','adc_zero'],default='header')
    a=p.parse_args();run(a.raw_dir,a.output_dir,a.protocol,a.records,a.mapping)
