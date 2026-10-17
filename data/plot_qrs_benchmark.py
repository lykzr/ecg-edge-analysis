"""从已保存的计分CSV出图；不重跑或调整算法，固定展示前10秒及首个内部错误。"""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ecg_dataset import load_record


def indices(path, column='index'):
    with path.open(encoding='utf-8', newline='') as stream:
        return [int(row[column]) for row in csv.DictReader(stream)]


def main(raw, result, record, model, output):
    if output.exists():
        raise FileExistsError('输出已存在，停止而不覆盖')
    samples, _, _ = load_record(raw, record, 'MLII')
    folder = result/record/model
    refs = indices(result/f'{record}_reference.csv')
    detected = indices(folder/'positions.csv')
    missed, extra = indices(folder/'missed.csv'), indices(folder/'extra.csv')
    errors = sorted(i for i in missed+extra if 3600 <= i < len(samples)-3600)
    start = max(0, errors[0]-1800) if errors else 0
    fig, axes = plt.subplots(2, 1, figsize=(14, 6), constrained_layout=True)
    for ax, lo, title in zip(axes, (0, start), ('First 10 seconds', 'First interior error (or first 10 seconds)')):
        hi = min(lo+3600, len(samples))
        ax.plot([i/360 for i in range(lo,hi)], [x/4096 for x in samples[lo:hi]], color='#384d60', linewidth=.8)
        for values, marker, color, label in ((refs,'o','#208050','Reference'),(detected,'x','#267ed2','Detected'),
                                              (missed,'v','#d22e2e','Missed'),(extra,'^','#d27612','Extra')):
            selected = [i for i in values if lo <= i < hi]
            ax.scatter([i/360 for i in selected], [samples[i]/4096 for i in selected],
                       marker=marker, color=color, s=25, label=label, facecolors='none' if marker=='o' else color)
        ax.set(xlabel='Time (s)', ylabel='MLII (mV)', title=title)
        ax.grid(alpha=.2)
        ax.legend(ncol=4, fontsize=8)
    fig.suptitle(f'MIT-BIH {record} / {model} / saved detections, no time shift')
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--result-dir', type=Path, required=True)
    parser.add_argument('--record', required=True)
    parser.add_argument('--model', default='v4')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.raw_dir, args.result_dir, args.record, args.model, args.output)
