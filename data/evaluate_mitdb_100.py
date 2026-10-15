"""评估官方 MIT-BIH 100：保留默认基线，支持固定幅值与无标注启动校准。"""
import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/reference'))
from ecg_reference import Config, Detector
from ecg_input import map_adc, calibrate
from ecg_peak_reference import PeakDetector


def decode212(data):
    if len(data) % 3:
        raise ValueError('212 数据长度不是三字节的整数倍')
    channels = [[], []]
    for a, b, c in zip(data[::3], data[1::3], data[2::3]):
        for channel, value in enumerate((a | ((b & 15) << 8), c | ((b >> 4) << 8))):
            channels[channel].append(value - 4096 if value & 2048 else value)
    return channels


def annotations(data):
    result, position, time = [], 0, 0
    while position < len(data):
        word = int.from_bytes(data[position:position+2], 'little')
        position += 2
        code, interval = word >> 10, word & 1023
        if not word:
            break
        if code == 59:
            high = int.from_bytes(data[position:position+2], 'little')
            low = int.from_bytes(data[position+2:position+4], 'little')
            delta = (high << 16) | low
            time += delta - (1 << 32) if delta & (1 << 31) else delta
            position += 4
        elif code == 63:
            position += interval + interval % 2
        elif code not in (60, 61, 62):
            time += interval
            result.append((time, code))
        if position > len(data):
            raise ValueError('标注文件被截断')
    return result


def match_beats(reference, detected, tolerance):
    # 有序一对一、固定容差匹配；不作事后整体平移，也不重复使用一个心搏。
    pairs, missed, extra = [], [], []
    i = j = 0
    while i < len(reference) and j < len(detected):
        delta = detected[j] - reference[i]
        if delta < -tolerance:
            extra.append(detected[j]); j += 1
        elif delta > tolerance:
            missed.append(reference[i]); i += 1
        else:
            pairs.append((i, j, delta)); i += 1; j += 1
    return pairs, missed + reference[i:], extra + detected[j:]


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f); writer.writerow(fields); writer.writerows(rows)


def run(raw, output, profile='baseline'):
    if output.exists():
        raise FileExistsError('输出目录已存在，停止避免覆盖')
    hashes = {}
    official = {line.split()[1].lstrip('*'): line.split()[0]
                for line in (raw/'SHA256SUMS.txt').read_text().splitlines()}
    for name in ('100.dat', '100.hea', '100.atr'):
        hashes[name] = hashlib.sha256((raw/name).read_bytes()).hexdigest()
        if hashes[name] != official[name]:
            raise ValueError(f'{name} 官方 SHA256 不匹配')
    header = (raw/'100.hea').read_text().splitlines()
    if header[0].split() != ['100', '2', '360', '650000']:
        raise ValueError('只支持已核查的 100 号记录')
    signals = decode212((raw/'100.dat').read_bytes())
    for channel, line in zip(signals, header[1:3]):
        fields = line.split()
        checksum = (sum(channel) + 32768) % 65536 - 32768
        if (fields[1] != '212' or len(channel) != 650000 or
                channel[0] != int(fields[5]) or checksum != int(fields[6])):
            raise ValueError('解码后的首值、采样数或 WFDB 校验和不匹配')
    all_annotations = annotations((raw/'100.atr').read_bytes())
    counts = Counter(code for _, code in all_annotations)
    # 本记录仅有 N、A、V 心搏，另有 + 节律标签；其他类型即停止复核。
    if counts != Counter({1: 2239, 8: 33, 5: 1, 28: 1}):
        raise ValueError(f'与官方 100 心搏组成不符：{counts}')
    reference = [index for index, code in all_annotations if code in (1, 5, 8)]
    config = Config()
    baseline = int(header[1].split()[4])
    gain = int(header[1].split()[2])
    calibration = None
    clipped = 0
    if profile in ('calibrated','peak'):
        samples, clipped = map_adc(signals[0], baseline, gain)
        config, calibration = calibrate(samples, config)
        amplitude = '(digital_ADC - baseline) * 4096 / gain; symmetric rounding; int16 saturation; no filtering'
        plot_gain = 4096
    elif profile == 'baseline':
        samples = [value - baseline for value in signals[0]]
        amplitude = '(digital_ADC - 1024), scale=1, no filtering'
        plot_gain = gain
    else:
        raise ValueError('未知评估配置')
    detector = PeakDetector(config) if profile == 'peak' else Detector(config)
    output.mkdir(parents=True)
    detected, event_rows, energies, thresholds = [], [], [], []
    independent_window = []
    independent_energy = 0
    for index, sample in enumerate(samples):
        state = detector.tick(sample)
        # 独立按原始差分重算窗口和，排除参考模型积分实现导致的零检出。
        if index:
            independent_window.append(abs(sample-samples[index-1]))
            independent_energy += independent_window[-1]
            if len(independent_window) > config.window_length:
                independent_energy -= independent_window.pop(0)
        if independent_energy != state.integrated_energy:
            raise AssertionError(f'第 {index} 点窗口和与参考模型不一致')
        energies.append(state.integrated_energy); thresholds.append(state.adaptive_threshold)
        if state.qrs_valid:
            detected.append(state.qrs_sample_index)
            event_rows.append((index, state.qrs_sample_index, state.rr_interval_samples))
        # 模拟样本间空拍，允许阈值输出更新；不推进采样计数。
        detector.tick(sample, valid=False)
    pairs, missed, extra = match_beats(reference, detected, 54)
    tp, fn, fp = len(pairs), len(missed), len(extra)
    errors = [delta * 1000 / 360 for _, _, delta in pairs]
    rr_errors = []
    for previous, current in zip(pairs, pairs[1:]):
        a, b, _ = previous; c, d, _ = current
        if c == a+1 and d == b+1:
            rr_errors.append(((detected[d]-detected[b])-(reference[c]-reference[a]))*1000/360)
    report = dict(record='100', lead='MLII', sampling_hz=360, samples=len(samples),
        duration_seconds=len(samples)/360, input=amplitude, profile=profile,
        clipped_samples=clipped, calibration=calibration,
        input_range=[min(samples), max(samples)], config=asdict(config),
        protocol='whole record, no warm-up exclusion; ordered one-to-one matching within +/-54 samples (150 ms); no offset correction',
        reference_beats=len(reference), annotation_codes=dict(counts), detected_beats=len(detected),
        diagnostic=dict(max_integrated_energy=max(energies), min_threshold=min(thresholds),
            max_threshold=max(thresholds), final_signal_level=detector.signal_level,
            final_noise_level=detector.noise_level, independent_window_check='PASS',
            samples_at_or_above_threshold=sum(e>=t for e,t in zip(energies,thresholds)),
            last_event_seconds=event_rows[-1][0]/360 if event_rows else None),
        TP=tp, FN=fn, FP=fp, sensitivity=tp/(tp+fn), positive_predictivity=tp/(tp+fp) if tp+fp else None,
        F1=2*tp/(2*tp+fn+fp),
        timing_ms=dict(mean=statistics.mean(errors), median=statistics.median(errors),
            mean_absolute=statistics.mean(map(abs, errors)), minimum=min(errors), maximum=max(errors)) if errors else None,
        rr_ms=dict(consecutive_matched_intervals=len(rr_errors),
            mean_absolute_error=statistics.mean(map(abs, rr_errors))) if rr_errors else None,
        source_sha256=hashes,
        implementation_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(), ROOT/'src/reference/ecg_reference.py',
                      ROOT/'src/reference/ecg_input.py', ROOT/'src/reference/ecg_peak_reference.py')},
        smoke_board_test='NOT_TESTED', scope='single-record offline baseline; no RTL/board/clinical validation')
    if calibration:
        start = calibration['samples']
        post_reference = [i for i in reference if i >= start]
        post_detected = [i for i in detected if i >= start]
        post_pairs, post_missed, post_extra = match_beats(post_reference, post_detected, 54)
        post_tp, post_fn, post_fp = len(post_pairs), len(post_missed), len(post_extra)
        report['after_calibration'] = dict(start_sample=start, reference_beats=len(post_reference),
            detected_beats=len(post_detected), TP=post_tp, FN=post_fn, FP=post_fp,
            sensitivity=post_tp/len(post_reference),
            positive_predictivity=post_tp/len(post_detected) if post_detected else None,
            F1=2*post_tp/(2*post_tp+post_fn+post_fp))
    reference_codes = [c for _,c in all_annotations if c in (1,5,8)]
    matched_types = Counter(reference_codes[i] for i,_,_ in pairs)
    report['beat_types'] = {str(code):dict(reference=counts[code],matched=matched_types[code])
                            for code in (1,5,8)}
    report['time_blocks'] = []
    for start in range(0,len(samples),5*60*360):
        end = min(start+5*60*360,len(samples))
        refs = [i for i in reference if start<=i<end]
        dets = [i for i in detected if start<=i<end]
        block_pairs,block_missed,block_extra = match_beats(refs,dets,54)
        report['time_blocks'].append(dict(start_seconds=start/360,end_seconds=end/360,
            TP=len(block_pairs),FN=len(block_missed),FP=len(block_extra)))
    delays = [(emission-position)*1000/360 for emission,position,_ in event_rows]
    report['confirmation_delay_ms'] = dict(minimum=min(delays),maximum=max(delays),
                                          mean=statistics.mean(delays)) if delays else None
    if profile == 'peak':
        checks = dict(sensitivity_at_least_99_percent=report['sensitivity']>=.99,
            positive_predictivity_at_least_99_percent=report['positive_predictivity'] is not None
                and report['positive_predictivity']>=.99,
            position_mae_at_most_10_ms=report['timing_ms'] is not None
                and report['timing_ms']['mean_absolute']<=10,
            rr_mae_at_most_15_ms=report['rr_ms'] is not None
                and report['rr_ms']['mean_absolute_error']<=15)
        report['development_gate'] = dict(result='PASS' if all(checks.values()) else 'FAIL',
            checks=checks, scope='provisional record-100 development check only; not independent validation')
    write_csv(output/'input.csv', ['sample'], ((x,) for x in samples))
    write_csv(output/'reference_beats.csv', ['index','code'], ((i,c) for i,c in all_annotations if c in (1,5,8)))
    write_csv(output/'events.csv', ['emission_index','index','rr_samples'], event_rows)
    write_csv(output/'matches.csv', ['reference_index','detected_index','error_samples'],
              ((reference[i],detected[j],delta) for i,j,delta in pairs))
    write_csv(output/'missed.csv', ['index'], ((i,) for i in missed))
    write_csv(output/'extra.csv', ['index'], ((i,) for i in extra))
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    windows = [(0,10,'First 10 seconds')]
    if missed:
        start = max(0, missed[len(missed)//2]/360-3)
        windows.append((start,start+6,'Example around an unmatched reference beat'))
    if extra:
        start = max(0,extra[0]/360-3)
        windows.append((start,start+6,'Example around an unmatched detection'))
    fig, axes = plt.subplots(len(windows)*2,1,figsize=(14,4*len(windows)),layout='constrained')
    for k,(start,end,title) in enumerate(windows):
        lo, hi = int(start*360), min(len(samples),int(end*360))
        t = [i/360 for i in range(lo,hi)]
        ax = axes[2*k]; ax.plot(t,[x/plot_gain for x in samples[lo:hi]],linewidth=.8)
        for values,color,label,marker in ((reference,'green','Reference','o'),(detected,'red','Detected','x')):
            idx = [i for i in values if lo<=i<hi]
            ax.scatter([i/360 for i in idx],[samples[i]/plot_gain for i in idx],c=color,marker=marker,label=label,s=25)
        ax.set(title=title,ylabel='MLII (mV)'); ax.legend(); ax.grid(alpha=.3)
        ax=axes[2*k+1]; ax.plot(t,energies[lo:hi],label='Integrated abs difference')
        ax.plot(t,thresholds[lo:hi],label='Threshold'); ax.set(xlabel='Time (s)',ylabel='Integer level'); ax.legend(); ax.grid(alpha=.3)
    fig.savefig(output/'comparison.png',dpi=140); plt.close(fig)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--profile', choices=['baseline','calibrated','peak'],default='baseline')
    args=parser.parse_args()
    run(args.raw_dir.resolve(),args.output_dir.resolve(),args.profile)
