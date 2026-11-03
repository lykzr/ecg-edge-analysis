"""将带time_s及mV导联列的连续CSV转换为网页500Hz标准CSV；不做高通。"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly


def convert(source, output, lead='MLII_mV', source_hz=360, segment_seconds=60):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not 1 <= source_hz <= 10000 or not 1 <= segment_seconds <= 60:
        raise ValueError('源采样率须为1—10000Hz，分段长度须为1—60秒整数')
    times, values = [], []
    with source.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not {'sample_index', 'time_s', lead}.issubset(reader.fieldnames or []):
            raise ValueError(f'需要sample_index、time_s、{lead}列；导联须明确为mV')
        if not lead.endswith('_mV'):
            raise ValueError('导联列名须以_mV结尾；不猜测ADC计数或单位')
        for index, row in enumerate(reader):
            if int(row['sample_index']) != index:
                raise ValueError(f'第{index}点序号不连续，不能跨缺样重采样')
            times.append(float(row['time_s']))
            values.append(float(row[lead]))
    times, values = np.asarray(times), np.asarray(values)
    if len(values) < 2 or not np.isfinite(times).all() or not np.isfinite(values).all():
        raise ValueError('至少需要两个有限样本，不能含NaN或无穷值')
    # 容许导出时间的小数舍入，不接受实际缺样或不规则时间轴。
    expected = times[0] + np.arange(len(times)) / source_hz
    if np.max(np.abs(times - expected)) > max(1e-7, .001 / source_hz):
        raise ValueError('时间轴与声明的源采样率不符；请核实采样率或缺样')
    divisor = math.gcd(source_hz, 500)
    mv = resample_poly(values, 500 // divisor, source_hz // divisor, padtype='line')
    scaled = mv * 4096
    codes = np.copysign(np.floor(np.abs(scaled) + .5), scaled)
    clipped = int(np.count_nonzero((codes < -32768) | (codes > 32767)))
    if clipped:
        raise ValueError(f'{clipped}点超出标准int16范围，停止转换；不会静默削波')
    codes = codes.astype(np.int16)
    # 所有校验完成后才创建输出目录；禁止覆盖已有结果。
    output.mkdir(parents=True, exist_ok=False)
    parts = []
    size = segment_seconds * 500
    for part, start in enumerate(range(0, len(codes), size), 1):
        path = output / f'{source.stem}_{lead}_500Hz_part{part:02d}.csv'
        chunk = codes[start:start + size]
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['index', 'sample', 'fs', 'scale'])
            writer.writerows((i, int(value), 500, 4096) for i, value in enumerate(chunk))
        parts.append(dict(file=path.name, samples=len(chunk), start_sample_500hz=start,
                          source_start_time_s=float(times[0] + start / 500),
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    result = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  source_file=source.name, lead=lead, input_unit='mV', source_hz=source_hz,
                  output_hz=500, scale=4096, input_samples=len(values), output_samples=len(codes),
                  resampling='scipy.signal.resample_poly; default Kaiser FIR; padtype=line',
                  rounding='nearest ties away from zero', clipped=clipped,
                  added_highpass=False, segments_are_independent_sessions=True,
                  note='仅格式转换与重采样；源数据既有滤波状态须由来源说明确认。分段分别重置检测/RR状态。未转换专家标注。',
                  parts=parts)
    (output / 'conversion.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='必须为不存在的新目录')
    parser.add_argument('--lead', default='MLII_mV')
    parser.add_argument('--source-hz', type=int, default=360)
    parser.add_argument('--segment-seconds', type=int, default=60)
    args = parser.parse_args()
    result = convert(args.input, args.output, args.lead, args.source_hz, args.segment_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
