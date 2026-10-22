"""固定厂商CSV的输入/滤波/阈值诊断；无标注时不计算检出率，不改板端参数。"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/pc'), str(ROOT/'src/reference')]
from ecg_capture_core import VendorCsv
from ecg_reference import Config, Detector
from ecg_filter_reference import Filter


def diagnose(values, config, trace=None):
    """逐样本实现与独立滑动差分和核对，保留全部启动和尾部。"""
    model = Detector(config)
    differences, events = [], []
    energy_max, threshold_min = 0, None
    total = 0
    for i, value in enumerate(values):
        state = model.tick(value)
        if i:
            difference = abs(value-values[i-1])
            differences.append(difference)
            total += difference
            if len(differences) > config.window_length:
                total -= differences[-config.window_length-1]
        if total >= 1 << config.energy_width:
            raise ValueError('独立能量超过位宽，诊断不允许掩盖回绕')
        if state.integrated_energy != total:
            raise AssertionError('参考模型与独立滑动能量不一致')
        energy_max = max(energy_max, total)
        threshold_min = state.adaptive_threshold if threshold_min is None else min(threshold_min, state.adaptive_threshold)
        if state.qrs_valid:
            events.append(dict(index=state.qrs_sample_index, rr=state.rr_interval_samples))
        if trace:
            trace.writerow([i, value, total, state.adaptive_threshold,
                            state.noise_level, state.signal_level, state.qrs_valid])
    # 无事件时signal不更新；对任意非负noise，阈值至少signal//4。
    floor = config.initial_signal_level//4
    return dict(samples=len(values), minimum=min(values), maximum=max(values),
                energy_max=energy_max, threshold_min=threshold_min,
                fixed_signal_threshold_floor=floor,
                below_fixed_signal_floor=energy_max < floor,
                event_count=len(events), events=events,
                independent_energy_equal=True)


def analyze(source, output):
    if output.exists():
        raise FileExistsError('输出目录已存在，不覆盖历史')
    reader = VendorCsv(source)
    samples = []
    try:
        while (sample := reader.read()) is not None:
            samples.append(sample)
        digest = reader.digest.hexdigest()
    finally:
        reader.close()
    signed = [s.pair[1] for s in samples]
    raw = [x >> 8 for x in signed]
    # 减首点仅用于验证常量基线/零状态滤波瞬态，不是幅值标定。
    centered = [(x-signed[0]) >> 8 for x in signed]
    if any(not -32768 <= x <= 32767 for x in raw+centered):
        raise ValueError('输入越界；本诊断不静默削顶')
    output.mkdir(parents=True)
    config = Config(sample_rate_hz=500)
    cases = {}
    series = dict(raw_shift8=raw, centered_shift8=centered)
    for name, values, profile in (
        ('bandpass_raw_shift8', raw, 'bandpass'),
        ('bandpass_centered_shift8', centered, 'bandpass'),
        ('bandpass_notch50_centered_shift8', centered, 'bandpass_notch')):
        filt = Filter(profile, sampling_hz=500, notch_hz=50)
        series[name] = [filt.tick(v) for v in values]
        cases[name] = dict(filter_clipped=filt.clipped)
    for name, values in series.items():
        with (output/(name+'.csv')).open('x', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['index','sample','energy','threshold','noise','signal','event'])
            details = diagnose(values, config, writer)
        cases.setdefault(name, {}).update(details)
    summary = dict(schema=1, source_sha256=digest, source_bytes=source.stat().st_size,
        source_samples=len(samples), time_first_s=samples[0].time_s, time_last_s=samples[-1].time_s,
        sample_rate_hz=500, channel='CH2 ECG', signed24_min=min(signed), signed24_max=max(signed),
        conversion='(offset24 - 8388608) >> 8; arithmetic floor shift; no mV calibration',
        centered_origin=signed[0], config=asdict(config), cases=cases,
        filter_contract=dict(highpass_hz=.5, lowpass_hz=40, notch_hz=50, notch_q=30,
                             implementation='existing independent RBJ float reference, zero initial state'),
        scope='diagnostic reproduction of already viewed unannotated CSV, not independent accuracy test',
        annotations_available=False, clinical_or_detection_accuracy=None,
        board_parameters_modified=False,
        provenance={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (Path(__file__), ROOT/'src/reference/ecg_reference.py',
                              ROOT/'src/reference/ecg_filter_reference.py', ROOT/'src/pc/ecg_capture_core.py')})
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.source,args.output),ensure_ascii=False))


if __name__ == '__main__':
    main()
