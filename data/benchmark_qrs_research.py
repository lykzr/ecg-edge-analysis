"""未合格研究快照的可移交回归入口；输出必须指定，不依赖既有tmp。"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/reference'))
import benchmark_qrs_v4 as base
from ecg_dataset import digest
from qrs_research import replay


def run(raw, output, protocol_path, stage):
    protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
    if protocol['evaluation_semantics'] != 'KNOWN_DATA_RESEARCH_NOT_INDEPENDENT':
        raise ValueError('研究数据不能改称独立测试')
    for name, sha in protocol['frozen_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('冻结来源发生变化：'+name)
    old_names, old_detect = base.IMPLEMENTATIONS, base.detect
    try:
        base.IMPLEMENTATIONS = list(protocol['frozen_sha256'])
        base.detect = lambda xs, name, p: replay(xs, p['candidate_config'])
        base.run(raw, output, protocol_path, stage, ['research'])
    finally:
        base.IMPLEMENTATIONS, base.detect = old_names, old_detect


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--stage', choices=['development', 'evaluation'], required=True)
    parser.add_argument('--protocol', type=Path, default=ROOT/'data/qrs_research_protocol.json')
    args = parser.parse_args()
    run(args.raw_dir, args.output_dir, args.protocol, args.stage)
