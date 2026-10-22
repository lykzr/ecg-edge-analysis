"""独立研究候选v5的完整已知记录回归；不改旧v4冻结基线，不称新独立测试。"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
import benchmark_qrs_v4 as base
from ecg_qrs_v5 import replay
from ecg_dataset import digest

def run(raw,output,protocol_path,stage):
    protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
    original=json.loads((ROOT/'data/qrs_v4_protocol.json').read_text(encoding='utf-8'))
    names=base.IMPLEMENTATIONS+['src/reference/ecg_qrs_v5.py','data/benchmark_qrs_v5.py','sim/test_qrs_v5.py']
    if set(protocol.get('frozen_sha256',{}))!=set(names):raise ValueError('v5依赖清单不完整')
    if any(digest(ROOT/n)!=h for n,h in protocol['frozen_sha256'].items()):raise ValueError('v5冻结源码变化，停止评分')
    for key in ['development_records','evaluation_records','lead','sampling_hz','units_per_mv','matching_tolerance_samples','gate','candidate_config']:
        if protocol[key]!=original[key]:raise ValueError('不能借候选修改原记录/计分/配置：'+key)
    if protocol.get('evaluation_semantics')!='KNOWN_DATA_CANDIDATE_REGRESSION':raise ValueError('必须声明已知数据复核')
    old_detect,old_names=base.detect,base.IMPLEMENTATIONS
    try:
        base.IMPLEMENTATIONS=names
        base.detect=lambda samples,name,p:replay(samples,p['candidate_config']) if name=='v5' else old_detect(samples,name,p)
        base.run(raw,output,protocol_path,stage,['v5'])
    finally:base.detect,base.IMPLEMENTATIONS=old_detect,old_names

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--stage',choices=['development','evaluation'],default='development')
    parser.add_argument('--protocol',type=Path,default=ROOT/'data/qrs_v5_protocol.json')
    args=parser.parse_args()
    run(args.raw_dir,args.output_dir,args.protocol,args.stage)
