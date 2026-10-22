"""冻结启动学习候选后的19条已知开发记录完整回归；不读取新独立测试或CNN数据。"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_auto import AutoDetector
from ecg_reference import Detector,Config
from ecg_dataset import load_record,metrics,BEAT_CODES


def evaluate(raw,output):
    output.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((ROOT/'data/qrs_v4_protocol.json').read_text(encoding='utf-8'))
    sources={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('src/reference/ecg_auto.py','src/rtl/ecg_qrs_auto.sv',str(Path(__file__).relative_to(ROOT)).replace('\\','/'))}
    (output/'protocol.json').write_text(json.dumps(dict(records=protocol['development_records'],config=asdict(Config()),
        bootstrap_seconds=2,scope='previously viewed development only, all samples including warmup, no tuning or time shift',sources=sources),indent=2),encoding='utf-8')
    result={}
    for record in protocol['development_records']:
        values,labels,info=load_record(raw,record,'MLII')
        reference=[i for i,c in labels if c in BEAT_CODES];codes=[c for i,c in labels if c in BEAT_CODES]
        original,candidate=Detector(),AutoDetector();old=[];new=[]
        for x in values:
            a=original.tick(x);b=candidate.feed_sample(x)
            if a.qrs_valid:old.append(a.qrs_sample_index)
            if b.qrs_valid:new.append(b.qrs_sample_index)
        met,pairs,missed,extra=metrics(reference,new,54)
        matched={i for i,j,delta in pairs}
        by_code={str(c):dict(count=codes.count(c),TP=sum(i in matched for i,code in enumerate(codes) if code==c)) for c in sorted(set(codes))}
        blocks=[]
        for start in range(0,len(values),60*360):
            stop=min(len(values),start+60*360)
            blocks.append(dict(start=start,stop=stop,metrics=metrics([i for i in reference if start<=i<stop],
                [i for i in new if start<=i<stop],54)[0]))
        row=dict(source=info,original=metrics(reference,old,54)[0],candidate=met,by_code=by_code,time_blocks=blocks,
                 candidate_events=new,missed_reference=missed,false_events=extra)
        result[record]=row
        (output/(record+'.json')).write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
        print(record,json.dumps(met),flush=True)
    tp=sum(x['candidate']['TP'] for x in result.values());fn=sum(x['candidate']['FN'] for x in result.values());fp=sum(x['candidate']['FP'] for x in result.values())
    summary=dict(scope='known 19-record development regression, not untouched test',records=len(result),TP=tp,FN=fn,FP=fp,
                 sensitivity=tp/(tp+fn),positive_predictivity=tp/(tp+fp),F1=2*tp/(2*tp+fn+fp),
                 final_qrs_gate_passed=False,note='本修复不替代v4完整门槛/噪声/定位/独立评估')
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(evaluate(args.raw,args.output),ensure_ascii=False))
