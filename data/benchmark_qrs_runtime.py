"""研究26运行时：完整已知记录等价/采样率实验；不访问分类独立测试。"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/reference'))
from ecg_qrs_runtime import InputRuntime, round_ratio
from ecg_beat_window import BeatCutter
from ecg_dataset import load_record, metrics, aggregate, BEAT_CODES, digest, write_csv


def run(raw, output, protocol_path, rate, reference_run=None):
    p = json.loads(protocol_path.read_text(encoding='utf-8'))
    for name, expected in p['source_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('冻结文件变化：' + name)
    if output.exists():
        raise FileExistsError('不覆盖旧实验目录')
    output.mkdir(parents=True)
    (output / 'protocol.json').write_bytes(protocol_path.read_bytes())
    report = dict(scope='KNOWN_DATA_DEVELOPMENT_REPRODUCTION', independent_test=False,
                  rate=rate, native_500hz_capture=False, board_test=False,
                  protocol_sha256=digest(protocol_path), source_sha256=p['source_sha256'],
                  environment=dict(python=platform.python_version()), rows=[])
    (output / 'checkpoint.json').write_text(json.dumps(dict(status='RUNNING', rate=rate)), encoding='utf-8')
    for stage in ('development', 'evaluation'):
        for record in p[stage + '_records']:
            started = time.monotonic()
            samples, labels, meta = load_record(raw, record, 'MLII')
            if rate == 500:
                import numpy as np
                from scipy.signal import resample_poly
                # 输入由已知360Hz记录离线构造，不冒称新500Hz/真实采集数据。
                up = resample_poly(np.asarray(samples, dtype=float), 25, 18)
                rounded = np.copysign(np.floor(np.abs(up) + .5), up)
                samples = np.clip(rounded, -32768, 32767).astype('int64').tolist()
            model = InputRuntime(rate)
            cutter = BeatCutter(rate)
            events = []
            beats = 0
            for sequence, sample in enumerate(samples):
                out = model.push(sample, sequence=sequence)
                events.extend(out)
                beats += len(cutter.push(sample, out, sequence=sequence))
            state = model.finish()
            cut_state = cutter.finish()
            refs = [round_ratio(i * rate, 360) for i, c in labels if c in BEAT_CODES]
            codes = [c for i, c in labels if c in BEAT_CODES]
            positions = [pos for _, pos, _ in events]
            scored, pairs, missed, extra = metrics(refs, positions, round_ratio(54 * rate, 360))
            for key in ('position_mae_ms', 'rr_mae_ms'):
                if scored[key] is not None:
                    scored[key] *= 360 / rate
            counts = Counter(codes)
            matched = Counter(codes[i] for i, _, _ in pairs)
            v = matched[5] / counts[5] if counts[5] else None
            gate = p['gate']
            checks = dict(sensitivity=scored['sensitivity'] is not None and scored['sensitivity'] >= gate['sensitivity'],
                          positive_predictivity=scored['positive_predictivity'] is not None and scored['positive_predictivity'] >= gate['positive_predictivity'],
                          position_mae=scored['position_mae_ms'] is not None and scored['position_mae_ms'] <= gate['position_mae_ms'],
                          rr_mae=scored['rr_mae_ms'] is not None and scored['rr_mae_ms'] <= gate['rr_mae_ms'],
                          v_recall=v is None or v >= gate['v_recall'])
            equal = None
            if reference_run is not None and rate == 360:
                path = reference_run / stage / record / 'research/events.csv'
                with path.open(newline='', encoding='utf-8') as stream:
                    saved = [tuple(int(row[k]) for k in ('emission_index', 'index', 'rr_samples'))
                             for row in csv.DictReader(stream)]
                equal = saved == events
            row = dict(record=record, stage=stage, **meta, **scored, source_samples=len(samples),
                       v_recall=v, v_reference=counts[5], v_matched=matched[5], checks=checks,
                       provisional_gate='PASS' if all(checks.values()) else 'FAIL',
                       reference_events_equal=equal, runtime=state, cut=cut_state, beats=beats,
                       seconds=time.monotonic() - started,
                       confirmation_delay_ms=max(((e-i)*1000/rate for e, i, _ in events), default=None))
            folder = output / record
            folder.mkdir()
            write_csv(folder / 'events.csv', ['emission_index', 'index', 'rr_samples'], events)
            write_csv(folder / 'missed.csv', ['index'], ((i,) for i in missed))
            write_csv(folder / 'extra.csv', ['index'], ((i,) for i in extra))
            row['time_blocks'] = [dict(start_seconds=s, TP=sum(s*rate <= refs[i] < (s+300)*rate for i, _, _ in pairs),
                FN=sum(s*rate <= i < (s+300)*rate for i in missed), FP=sum(s*rate <= i < (s+300)*rate for i in extra))
                for s in range(0, (len(samples) + rate - 1)//rate, 300)]
            (folder / 'summary.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
            report['rows'].append(row)
            (output / 'checkpoint.json').write_text(json.dumps(dict(status='RUNNING', completed=len(report['rows']), last=record)), encoding='utf-8')
            print(record, rate, {k: row[k] for k in ('TP', 'FN', 'FP', 'v_recall', 'reference_events_equal')}, flush=True)
    report['aggregate'] = aggregate(report['rows'])
    report['all_reference_events_equal'] = all(r['reference_events_equal'] is True for r in report['rows'])
    report['qualified'] = False
    report['status'] = 'DONE'
    (output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (output / 'checkpoint.json').write_text(json.dumps(dict(status='DONE', completed=len(report['rows']))), encoding='utf-8')
    print('DONE', json.dumps(report['aggregate']), 'events_equal', report['all_reference_events_equal'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=ROOT / 'data/qrs_runtime_protocol.json')
    parser.add_argument('--rate', type=int, choices=(360, 500), default=360)
    parser.add_argument('--reference-run', type=Path)
    args = parser.parse_args()
    run(args.raw_dir, args.output_dir, args.protocol, args.rate, args.reference_run)
