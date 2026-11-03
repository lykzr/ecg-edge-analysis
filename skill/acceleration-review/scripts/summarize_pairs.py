"""汇总已配对的同精度计时；不一致不输出有效加速比。"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys


def summarize(pairs, metadata):
    pairs, metadata = Path(pairs), Path(metadata)
    m = json.loads(metadata.read_text(encoding='utf-8-sig'))
    for key in ('input_sha256', 'model_sha256'):
        if not isinstance(m.get(key), str) or not re.fullmatch(r'[0-9a-fA-F]{64}', m[key]):
            raise ValueError('缺少有效来源哈希：' + key)
    for key in ('precision', 'reference_label', 'accelerator_label', 'scope'):
        if not isinstance(m.get(key), str) or not m[key].strip():
            raise ValueError('缺少实验合同：' + key)
    for key in ('reference_timer_hz', 'accelerator_timer_hz'):
        value = m.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('计时频率必须为正有限数：' + key)
    total_ref = total_acc = mismatches = count = 0
    seen = set()
    with pairs.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['sample_id', 'reference_ticks', 'accelerator_ticks', 'output_match']:
            raise ValueError('CSV表头不符合配对合同')
        for row in reader:
            if None in row or any(v is None or not v.strip() for v in row.values()):
                raise ValueError('缺失或多余字段')
            if row['sample_id'] in seen:
                raise ValueError('重复任务：' + row['sample_id'])
            seen.add(row['sample_id'])
            ticks = []
            for key in ('reference_ticks', 'accelerator_ticks'):
                if not re.fullmatch(r'[1-9][0-9]*', row[key]):
                    raise ValueError('ticks须规范正整数：' + key)
                ticks.append(int(row[key]))
            if row['output_match'] not in ('0', '1'):
                raise ValueError('output_match只能是0或1')
            total_ref += ticks[0]
            total_acc += ticks[1]
            count += 1
            mismatches += row['output_match'] == '0'
    if not count:
        raise ValueError('无有效任务，不能计算加速比')
    ref = total_ref / m['reference_timer_hz']
    acc = total_acc / m['accelerator_timer_hz']
    if not all(math.isfinite(v) and v > 0 for v in (ref, acc, ref / acc)):
        raise ValueError('时长或比值超出有限正数范围')
    return dict(passed=mismatches == 0, tasks=count, mismatches=mismatches,
                reference_total_ticks=total_ref, accelerator_total_ticks=total_acc,
                reference_total_ms=ref * 1000, accelerator_total_ms=acc * 1000,
                reference_mean_ms=ref * 1000 / count, accelerator_mean_ms=acc * 1000 / count,
                speedup=ref / acc if mismatches == 0 else None, contract=m,
                paired_sha256=hashlib.sha256(pairs.read_bytes()).hexdigest(),
                metadata_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),
                scope='supplied paired timings only; no inference or independent correctness verification')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pairs', required=True)
    p.add_argument('--metadata', required=True)
    a = p.parse_args()
    try:
        result = summarize(a.pairs, a.metadata)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, csv.Error) as error:
        result = dict(passed=False, error=str(error))
    print(json.dumps(result, ensure_ascii=True))
    sys.exit(0 if result['passed'] else 1)
