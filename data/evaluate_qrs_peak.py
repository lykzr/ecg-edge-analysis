"""冻结原波形确认候选后的完整已知开发回归，不读取独立评估/CNN集合。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_peak import PeakDetector
from ecg_dataset import load_record,metrics,BEAT_CODES


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(raw,output,baseline):
    output.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((ROOT/'data/qrs_v4_protocol.json').read_text())
    sources=['src/reference/ecg_peak.py','src/reference/ecg_auto.py','src/reference/ecg_reference.py',
             'src/reference/ecg_input.py','src/reference/ecg_filter_reference.py',
             'data/ecg_dataset.py','data/evaluate_qrs_peak.py']
    (output/'protocol.json').write_text(json.dumps(dict(records=protocol['development_records'],gate=protocol['gate'],
        matching_tolerance=54,input='same map_adc as stored auto baseline',startup_scored=True,tail_scored=True,
        source_sha256={p:sha(ROOT/p) for p in sources},baseline=str(baseline),
        python=sys.version,role='known development; no untouched-test claim; no post-hoc shift'),indent=2)+'\n',encoding='utf-8')
    rows=[]
    for record in protocol['development_records']:
        values,labels,info=load_record(raw,record,'MLII')
        old=json.loads((baseline/(record+'.json')).read_text());assert old['source']==info
        detector=PeakDetector();events=[]
        for value in values:events.extend(detector.push(value))
        positions=[e.position for e in events]
        assert positions==sorted(set(positions)) and all(0<=e.position<=e.emitted<len(values) for e in events)
        refs=[i for i,c in labels if c in BEAT_CODES];codes=[c for i,c in labels if c in BEAT_CODES]
        met,pairs,missed,extra=metrics(refs,positions,54);matched={i for i,j,d in pairs}
        by_code={str(c):dict(count=codes.count(c),TP=sum(i in matched for i,code in enumerate(codes) if code==c)) for c in sorted(set(codes))}
        v=by_code.get('5',dict(count=0,TP=0));met['v_recall']=v['TP']/v['count'] if v['count'] else None
        met['gate_passed']=all(met[k] is not None and (met[k]<=limit if k.endswith('_ms') else met[k]>=limit)
            for k,limit in protocol['gate'].items() if k!='v_recall' or v['count'])
        blocks=[]
        for start in range(0,len(values),60*360):
            stop=min(len(values),start+60*360)
            blocks.append(dict(start=start,stop=stop,metrics=metrics([i for i in refs if start<=i<stop],[i for i in positions if start<=i<stop],54)[0]))
        row=dict(record=record,source=info,baseline=old['candidate'],baseline_sha256=sha(baseline/(record+'.json')),
            candidate=met,by_code=by_code,time_blocks=blocks,events=[e.__dict__ for e in events],
            missed_reference=missed,false_events=extra,rejected=detector.rejected,
            max_pending=detector.max_pending,tail_pending=len(detector.pending),
            event_age_max=max((e.emitted-e.position for e in events),default=None),
            confirmation_delay_ms=dict(mean=sum((e.emitted-e.position)*1000/360 for e in events)/len(events),
                minimum=min((e.emitted-e.position)*1000/360 for e in events),
                maximum=max((e.emitted-e.position)*1000/360 for e in events)) if events else None)
        (output/(record+'.json')).write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8');rows.append(row)
        print(record,json.dumps(met),flush=True)
    tp,fn,fp=(sum(r['candidate'][key] for r in rows) for key in ('TP','FN','FP'))
    rr_count=sum(r['candidate']['matched_rr_intervals'] for r in rows)
    vcount=sum(r['by_code'].get('5',dict(count=0))['count'] for r in rows)
    vtp=sum(r['by_code'].get('5',dict(TP=0))['TP'] for r in rows)
    summary=dict(records=len(rows),TP=tp,FN=fn,FP=fp,sensitivity=tp/(tp+fn),positive_predictivity=tp/(tp+fp),
        F1=2*tp/(2*tp+fn+fp),position_mae_ms=sum(r['candidate']['position_mae_ms']*r['candidate']['TP'] for r in rows if r['candidate']['TP'])/tp,
        rr_mae_ms=sum(r['candidate']['rr_mae_ms']*r['candidate']['matched_rr_intervals'] for r in rows if r['candidate']['matched_rr_intervals'])/rr_count,
        v_recall=vtp/vcount,records_passing=sum(r['candidate']['gate_passed'] for r in rows),
        scope='known development software-only, no RTL/board/independent claim',final_qrs_gate_passed=False)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(evaluate(args.raw,args.output,args.baseline)))
