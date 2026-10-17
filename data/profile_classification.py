"""盘点分类候选标签与切拍边界，不训练、不划分CNN集合、不改QRS协议。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from ecg_dataset import annotations, BEAT_CODES

ROOT=Path(__file__).resolve().parents[1]
# 候选研究分组；N包含束支阻滞和逸搏，不能把整个N组叫作健康/正常人。
GROUPS={'N':{1,2,3,11,34},'S':{4,7,8,9},'V':{5,10},'F':{6}}


def profile(raw, protocol, output, before=96, after=160):
    if output.exists():
        raise FileExistsError('输出已存在，停止避免覆盖')
    if before<1 or after<1:
        raise ValueError('切拍长度必须为正')
    p=json.loads(protocol.read_text(encoding='utf-8'))
    records=p['development_records']+p['evaluation_records']
    if len(records)!=len(set(records)):
        raise ValueError('记录重复')
    official={line.split()[1].lstrip('*'):line.split()[0] for line in (raw/'SHA256SUMS.txt').read_text().splitlines()}
    rows=[]; total=Counter(); label_counts=Counter(); excluded=Counter()
    for record in records:
        hashes={}
        for ext in ('hea','dat','atr'):
            name=f'{record}.{ext}'
            hashes[name]=hashlib.sha256((raw/name).read_bytes()).hexdigest()
            if hashes[name]!=official[name]:
                raise ValueError(f'{name}官方SHA256不匹配')
        header=(raw/f'{record}.hea').read_text().splitlines()[0].split()
        if header[:3]!=[record,'2','360']:
            raise ValueError('仅支持已核查的360Hz双导联记录')
        length=int(header[3]); counts=Counter(); usable=Counter(); unknown=Counter(); boundary=Counter()
        for index,code in annotations((raw/f'{record}.atr').read_bytes()):
            if code not in BEAT_CODES:
                continue
            label_counts[code]+=1
            group=next((name for name,codes in GROUPS.items() if code in codes),None)
            if group is None:
                unknown[code]+=1;excluded[code]+=1
                continue
            counts[group]+=1;total[group]+=1
            if index-before>=0 and index+after<=length:
                usable[group]+=1
            else:
                boundary[group]+=1
        rows.append(dict(record=record,candidate_counts=dict(counts),full_window_counts=dict(usable),
                         boundary_excluded=dict(boundary),unmapped_beat_codes=dict(unknown),source_sha256=hashes))
    result=dict(scope='TASK_DESIGN_AUDIT_NOT_TRAINING_OR_TEST_SCORE',records=len(rows),
        record_pool_source=protocol.relative_to(ROOT).as_posix() if protocol.is_relative_to(ROOT) else str(protocol),
        cnn_split='NOT_DEFINED; QRS development/evaluation roles are not a CNN split',
        groups={k:sorted(v) for k,v in GROUPS.items()},candidate_counts=dict(total),
        all_beat_code_counts=dict(label_counts),unmapped_beat_code_counts=dict(excluded),
        window_proposal=dict(sampling_hz=360,before_samples=before,after_samples=after,length=before+after,
                             interval='[annotation-before, annotation+after)',normalization='NOT_DEFINED'),
        rows=rows,trained=False,smoke_board_test='NOT_TESTED')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='')
    print(json.dumps({k:result[k] for k in ('records','candidate_counts','unmapped_beat_code_counts','trained')},ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--record-pool-protocol',type=Path,default=ROOT/'data/qrs_v4_protocol.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    profile(args.raw_dir,args.record_pool_protocol,args.output)
