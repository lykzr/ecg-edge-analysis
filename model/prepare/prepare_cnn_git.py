"""Git克隆后的开发数据下载/准备；无父缓存、ZIP、权重或独立测试读取依赖。"""
import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'data'))
sys.path.insert(0,str(ROOT/'model/prepare'))
from download_external_ecg import retrieve, retrieve_waveform


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_digest(array):
    # 字符串以值而非NumPy预分配宽度比较；浮点/整数保持原字节。
    header = json.dumps({'shape': list(array.shape), 'kind': array.dtype.kind}, sort_keys=True).encode()
    data = json.dumps(array.tolist(), ensure_ascii=False, separators=(',', ':')).encode() if array.dtype.kind in 'US' else array.tobytes()
    return hashlib.sha256(header + b'\n' + data).hexdigest()


def validate_protocol(p):
    held = set(p['excluded_independent_test_subjects'])
    flat = [s for group in p['folds'] for s in group]
    if len(flat) != len(set(flat)) or held & set(flat):
        raise ValueError('开发折重复或包含保留测试患者')
    for role in ('development_records', 'auxiliary_records'):
        rows = p[role]
        if len({(r['database'], r['record']) for r in rows}) != len(rows):
            raise ValueError('记录重复')
        if held & {r['subject'] for r in rows}:
            raise ValueError('禁止获取保留测试患者')
    if {r['subject'] for r in p['development_records']} != set(flat):
        raise ValueError('开发记录和折不一致')
    if any(r['database'] != 'mitdb' for r in p['auxiliary_records']):
        raise ValueError('此Git入口只复现verified来源')


def download(p, raw):
    validate_protocol(p)
    for row in p['development_records'] + p['auxiliary_records']:
        database = row['database']; directory = raw / database
        directory.mkdir(parents=True, exist_ok=True)
        base = f'https://physionet.org/files/{database}/1.0.0/'
        official = {Path(k).name: v for k, v in p['raw_sha256'].items() if k.startswith(database + '/')}
        for ext in ('hea', 'atr', 'dat'):
            name = row['record'] + '.' + ext
            if ext == 'dat':
                retrieve_waveform(directory, name, base, official)
            else:
                retrieve(directory, name, base, official)
        print(json.dumps({'download_verified': database + ':' + row['record']}), flush=True)


def records(rows, p, raw, cap):
    import numpy as np
    import wfdb
    from prepare_cnn_expanded import BEATS, common_window, causal_rr
    values = defaultdict(list)
    mapping = {symbol: i for i, symbols in enumerate(p['label_symbols'].values()) for symbol in symbols}
    for row in rows:
        database = row['database']; record = row['record']; key = database + ':' + record
        folder = raw / database
        for ext in ('dat', 'hea', 'atr'):
            path = folder / (record + '.' + ext)
            if digest(path) != p['raw_sha256'][database + '/' + path.name]:
                raise ValueError('冻结原始文件校验失败：' + str(path))
        h = wfdb.rdheader(str(folder / record)); channel = h.sig_name.index(row['lead'])
        if h.fs != row['fs'] or h.units[channel] != 'mV' or h.adc_gain[channel] <= 0:
            raise ValueError('导联、采样率或物理幅值不符')
        if database == 'incartdb' and 'patient ' + row['subject'].split(':')[1] not in h.comments:
            raise ValueError('患者身份不符')
        d = wfdb.rdrecord(str(folder / record), channels=[channel], physical=False).d_signal[:, 0]
        if int(d[0]) != h.init_value[channel] or (int(d.astype(np.int64).sum()) - h.checksum[channel]) % 65536:
            raise ValueError('首值/校验和不符')
        signal = (d.astype(np.float64) - h.baseline[channel]) / h.adc_gain[channel]
        if not np.isfinite(signal).all():
            raise ValueError('非有限输入')
        ann = wfdb.rdann(str(folder / record), 'atr'); previous = None; history = deque(maxlen=401)
        for index, symbol in zip(ann.sample, ann.symbol):
            index = int(index)
            if symbol not in BEATS:
                continue
            if previous is None:
                previous = index
                continue
            delta = index - previous; previous = index
            if delta <= 0:
                raise ValueError('非正RR')
            history.append(delta / h.fs)
            if symbol not in mapping:
                continue
            x = common_window(signal, index, h.fs, p['window'])
            if x is None:
                continue
            sample = {'x': x, 'rr': causal_rr(list(history)), 'y': mapping[symbol], 'record': key,
                      'subject': row['subject'], 'r_index': index, 'code': symbol, 'sampling_unit': row['subject']}
            for name, value in sample.items():
                values[name].append(value)
        print(json.dumps({'prepared_record': key}), flush=True)
    arrays = {k: np.asarray(v, dtype=np.float32 if k in ('x', 'rr') else np.int64 if k in ('y', 'r_index') else None)
              for k, v in values.items()}
    if cap:
        chosen = []
        for subject in sorted(set(arrays['subject'])):
            for cls, limit in enumerate(p['train_sampling']['per_verified_subject_per_class']):
                ids = np.flatnonzero((arrays['subject'] == subject) & (arrays['y'] == cls))
                ids = sorted(ids, key=lambda i: hashlib.sha256(
                    f"{p['train_sampling']['seed']}:{arrays['record'][i]}:{arrays['r_index'][i]}".encode()).digest())
                chosen.extend(ids[:limit])
        take = np.array(sorted(chosen), dtype=np.int64)
        arrays = {k: v[take] for k, v in arrays.items()}
    return arrays


def prepare(p, protocol, raw, output):
    import numpy as np
    validate_protocol(p)
    if output.exists():
        raise FileExistsError('不覆盖缓存')
    output.mkdir(parents=True)
    shutil.copyfile(protocol, output / 'protocol.json')
    manifest = {'protocol_sha256': digest(protocol), 'test_access': 'NOT_LOADED',
                'scope': 'v8 residual_verified inputs rebuilt from official raw; no auxiliary unknown sources',
                'source_data_sha256': p['raw_sha256'], 'smoke_board_test': 'NOT_TESTED'}
    for role, key in (('development', 'development_records'), ('auxiliary', 'auxiliary_records')):
        arrays = records(p[key], p, raw, role == 'auxiliary')
        actual = {name: array_digest(a) for name, a in arrays.items()}
        if actual != p['expected_array_sha256'][role]:
            raise ValueError('重建张量未逐值复现冻结v8输入；不自动放宽容差或更新预期')
        np.savez_compressed(output / (role + '.npz'), **arrays)
        manifest[role + '_sha256'] = digest(output / (role + '.npz'))
        manifest[role + '_examples'] = len(arrays['y'])
        manifest[role + '_counts'] = np.bincount(arrays['y'], minlength=4).tolist()
    manifest['source_sha256'] = {}
    for file in ('model/prepare/prepare_cnn_git.py', 'model/prepare/prepare_cnn_expanded.py', 'model/prepare/download_external_ecg.py'):
        dest = output / 'source_snapshot' / file; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / file, dest); manifest['source_sha256'][file] = digest(ROOT / file)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('source_data_sha256', 'source_sha256')}, ensure_ascii=False))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage', choices=('download', 'prepare'))
    ap.add_argument('--protocol', type=Path, default=ROOT / 'model/protocols/cnn_git_v1_protocol.json')
    ap.add_argument('--raw-dir', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path)
    args = ap.parse_args(); p = json.loads(args.protocol.read_text(encoding='utf-8'))
    if args.stage == 'download':
        download(p, args.raw_dir)
    else:
        if args.output_dir is None:
            ap.error('prepare需要--output-dir')
        prepare(p, args.protocol, args.raw_dir, args.output_dir)
