"""v4统一计分入口；保留v3原脚本及其失败快照，冻结后再检查新记录。"""
import argparse
from collections import Counter
import importlib
import inspect
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_dataset import BEAT_CODES, digest, load_record, metrics, write_csv, aggregate

IMPLEMENTATIONS = ['data/benchmark_qrs_v4.py', 'data/ecg_dataset.py', 'src/reference/ecg_qrs_v4.py', 'src/reference/gqrs_stream.py', 'src/reference/ecg_input.py', 'src/reference/ecg_filter_reference.py', 'src/third_party/gqrs_core.py', 'src/third_party/gqrs_provenance.json', 'src/third_party/wfdb_license.txt', 'build/extract_gqrs_core.py', 'data/requirements_qrs.txt']


def detect(samples, name, protocol):
    if name=='gqrs':
        import numpy as np
        import wfdb
        from wfdb import processing
        positions = processing.gqrs_detect(d_sig=np.asarray(samples,dtype='int64'),fs=360,adc_gain=4096,adc_zero=0)
        return [int(i) for i in positions],None,dict(wfdb_version=wfdb.__version__,
            source_sha256=digest(Path(inspect.getfile(processing.gqrs_detect))),
            causality='OFFLINE_GQRS_DEFAULT_LEARNING',parameters='WFDB 4.3.1 GQRS defaults; no peak correction')
    if name=='xqrs':
        import numpy as np
        import wfdb
        from wfdb import processing
        if wfdb.__version__!=protocol['wfdb_version']:
            raise ValueError('WFDB版本与协议不符')
        positions = processing.xqrs_detect(np.asarray(samples,dtype=float)/4096,360,learn=True,verbose=False)
        return [int(i) for i in positions],None,dict(wfdb_version=wfdb.__version__,
            source_sha256=digest(Path(inspect.getfile(processing.XQRS))),
            causality='OFFLINE_FULL_RECORD_FILTFILT',parameters='WFDB 4.3.1 defaults; learn=True; no peak correction')
    if name=='v4':
        module = importlib.import_module('ecg_qrs_v4')
        return module.replay(samples,protocol.get('candidate_config',{}))
    raise ValueError('当前入口只保留v4/xqrs/gqrs；历史对照请使用归档入口')


def run(raw, output, protocol_path, stage, models):
    if output.exists():
        raise FileExistsError('输出存在，停止而不覆盖')
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    if set(protocol['development_records'])&set(protocol['evaluation_records']):
        raise ValueError('开发与新记录集合重叠')
    import wfdb
    from wfdb.processing.qrs import GQRS
    upstream_hash = digest(Path(inspect.getfile(GQRS)))
    if wfdb.__version__!=protocol['wfdb_version']:
        raise ValueError('WFDB版本与协议不符')
    if stage=='evaluation' and ('v4' in models):
        if (set(protocol.get('frozen_sha256',{}))!=set(IMPLEMENTATIONS) or 'candidate_config' not in protocol
            or any(digest(ROOT/n)!=h for n,h in protocol['frozen_sha256'].items())
            or protocol.get('wfdb_source_sha256')!=upstream_hash):
            raise ValueError('v4独立评估前必须冻结实现和参数')
    output.mkdir(parents=True)
    (output/'protocol.json').write_bytes(protocol_path.read_bytes())
    source_names = IMPLEMENTATIONS
    report = dict(stage=stage,protocol=protocol,protocol_sha256=digest(protocol_path),rows=[],
                  implementation_sha256={n:digest(ROOT/n) for n in source_names},
                  wfdb_source_sha256=upstream_hash,
                  smoke_board_test='NOT_TESTED',scope='offline software scoring; XQRS is not real-time')
    import numpy,scipy,wfdb,matplotlib
    report['environment'] = dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,wfdb=wfdb.__version__,matplotlib=matplotlib.__version__)
    for record in protocol[stage+'_records']:
        samples,labels,metadata = load_record(raw,record,protocol['lead'])
        refs = [i for i,c in labels if c in BEAT_CODES]
        codes = [c for _,c in labels if c in BEAT_CODES]
        write_csv(output/f'{record}_reference.csv',['index','code'],zip(refs,codes))
        for name in models:
            positions,events,details = detect(samples,name,protocol)
            if positions!=sorted(set(positions)) or any(i<0 or i>=len(samples) for i in positions):
                raise ValueError('检出位置重复、乱序或越界')
            m,pairs,missed,extra = metrics(refs,positions,protocol['matching_tolerance_samples'])
            counts,matched = Counter(codes),Counter(codes[i] for i,_,_ in pairs)
            v_recall = matched[5]/counts[5] if counts[5] else None
            gate = protocol['gate']
            checks = dict(sensitivity=m['sensitivity'] is not None and m['sensitivity']>=gate['sensitivity'],
                positive_predictivity=m['positive_predictivity'] is not None and m['positive_predictivity']>=gate['positive_predictivity'],
                position_mae=m['position_mae_ms'] is not None and m['position_mae_ms']<=gate['position_mae_ms'],
                rr_mae=m['rr_mae_ms'] is not None and m['rr_mae_ms']<=gate['rr_mae_ms'],
                v_recall=v_recall is None or v_recall>=gate['v_recall'])
            row = dict(record=record,model=name,role=stage,**metadata,**m,details=details,v_recall=v_recall,
                beat_types={str(c):dict(reference=counts[c],matched=matched[c]) for c in counts},
                checks=checks,provisional_gate='PASS' if all(checks.values()) else 'FAIL')
            if events is not None:
                delays = [(e-i)*1000/360 for e,i,_ in events]
                row['sample_confirmation_delay_ms'] = dict(mean=statistics.mean(delays),minimum=min(delays),maximum=max(delays)) if delays else None
            folder = output/record/name
            folder.mkdir(parents=True)
            write_csv(folder/'positions.csv',['index'],((i,) for i in positions))
            if events is not None:
                write_csv(folder/'events.csv',['emission_index','index','rr_samples'],events)
            write_csv(folder/'matches.csv',['reference_index','detected_index','error_samples'],((refs[i],positions[j],d) for i,j,d in pairs))
            write_csv(folder/'missed.csv',['index'],((i,) for i in missed))
            write_csv(folder/'extra.csv',['index'],((i,) for i in extra))
            row['time_blocks'] = [dict(start_seconds=start/360,end_seconds=min(start+108000,len(samples))/360,
                TP=sum(start<=refs[i]<start+108000 for i,_,_ in pairs),
                FN=sum(start<=i<start+108000 for i in missed),FP=sum(start<=i<start+108000 for i in extra)) for start in range(0,len(samples),108000)]
            (folder/'summary.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8')
            report['rows'].append(row)
            print(record,name,{k:row[k] for k in ['TP','FN','FP','position_mae_ms','v_recall']},flush=True)
    report['aggregate'] = {}
    for name in models:
        rows = [r for r in report['rows'] if r['model']==name]
        summary = aggregate(rows)
        total = sum(r['beat_types'].get('5',{}).get('reference',0) for r in rows)
        matched = sum(r['beat_types'].get('5',{}).get('matched',0) for r in rows)
        summary.update(v_reference=total,v_matched=matched,v_recall=matched/total if total else None)
        report['aggregate'][name] = summary
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DONE',report['aggregate'],flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--protocol',type=Path,default=ROOT/'data/qrs_v4_protocol.json')
    parser.add_argument('--stage',choices=['development','evaluation'],default='development')
    parser.add_argument('--models',nargs='+',default=['v4','xqrs','gqrs'],choices=['v4','xqrs','gqrs'])
    args = parser.parse_args()
    run(args.raw_dir,args.output_dir,args.protocol,args.stage,args.models)
