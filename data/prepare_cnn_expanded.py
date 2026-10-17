"""扩展分类数据：先仅按元数据冻结受试者划分，再准备匹配波形缓存。"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from scipy.signal import resample_poly, firwin
import scipy
import wfdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data'))
from download_external_ecg import checksum_map

LABELS = {'N': list('NLRje'), 'S': list('aJAS'), 'V': list('VE'), 'F': ['F']}
BEATS = set('NLRaVFJASE/j eQn?fBr').difference(' ')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def validate_splits(splits):
    seen_records = set()
    roles = {}
    for split, rows in splits.items():
        for row in rows:
            key = row['database'] + ':' + row['record']
            if key in seen_records:
                raise ValueError('记录重复或跨集合：' + key)
            seen_records.add(key)
            subject = row['subject']
            if subject in roles and roles[subject] != split:
                raise ValueError('受试者跨集合：' + subject)
            roles[subject] = split
            if row['database'] == 'svdb' and split != 'train':
                raise ValueError('身份不明确SVDB只允许辅助训练')
    if set(splits) != {'train', 'validation', 'test'}:
        raise ValueError('必须三个集合')


def audit(raw):
    rows = []
    sources = {}
    for db in ('incartdb', 'svdb'):
        directory = raw / db
        official = checksum_map((directory / 'SHA256SUMS.txt').read_bytes())
        records = (directory / 'RECORDS').read_text().split()
        for record in records:
            for ext in ('hea', 'atr'):
                path = directory / (record + '.' + ext)
                if digest(path) != official[path.name]:
                    raise ValueError('元数据SHA变化：' + str(path))
                sources[db + '/' + path.name] = digest(path)
            header = wfdb.rdheader(str(directory / record))
            if db == 'incartdb':
                match = re.search(r'^patient (\d+)$', '\n'.join(header.comments), re.M)
                if not match:
                    raise ValueError('缺INCART受试者身份')
                subject = 'incart:' + match[1]
                lead = 'II'
                # 对照官方独立患者映射，不只信单个头文件。
                mapping = (directory / 'files-patients-diagnoses.txt').read_text()
                section = re.search(r'^patient ' + match[1] + r'\n([^\n]+)', mapping, re.M)
                if section is None or record not in section[1].split():
                    raise ValueError('官方受试者映射冲突')
            else:
                subject = 'svdb:identity_unknown_pool'
                lead = 'ECG1'
            if lead not in header.sig_name:
                raise ValueError('导联缺失')
            counts = Counter(wfdb.rdann(str(directory / record), 'atr').symbol)
            rows.append({'database': db, 'record': record, 'subject': subject, 'lead': lead,
                         'fs': header.fs, 'samples': header.sig_len,
                         'counts': {k: sum(counts[s] for s in symbols) for k, symbols in LABELS.items()},
                         'all_symbols': dict(counts)})
    return rows, sources


def choose_patients(rows, seed):
    """固定种子，元数据分层；目标/约束均在训练和信号读取前决定。"""
    counts = defaultdict(lambda: np.zeros(4))
    for r in rows:
        if r['database'] == 'incartdb':
            counts[r['subject']] += [r['counts'][k] for k in LABELS]
    names = sorted(counts)
    matrix = np.array([counts[n] for n in names])
    rng = np.random.default_rng(seed)
    best = None
    targets = np.array([20, 6, 6]) / 32
    for _ in range(20000):
        perm = rng.permutation(32)
        groups = (perm[:20], perm[20:26], perm[26:])
        sums = np.array([matrix[g].sum(axis=0) for g in groups])
        present = np.array([(matrix[g] > 0).sum(axis=0) for g in groups])
        if np.any(present[:, 1] < 3) or np.any(present[:, 3] < 3) or np.any(sums[1:, 1] < 100):
            continue
        cost = float(np.square(sums / matrix.sum(axis=0) - targets[:, None]).sum())
        if best is None or cost < best[0]:
            best = (cost, groups)
    if best is None:
        raise ValueError('标注支持不足，不能自动放松分层约束')
    assignment = {names[i]: role for role, group in zip(('train', 'validation', 'test'), best[1]) for i in group}
    return assignment, {'seed': seed, 'draws': 20000, 'minimum_S_and_F_subjects_per_role': 3,
                        'minimum_S_beats_in_validation_or_test': 100,
                        'target_subject_counts': [20, 6, 6], 'annotation_balance_cost': best[0]}


def freeze(raw, output):
    rows, hashes = audit(raw)
    assignment, design = choose_patients(rows, 2026101706)
    splits = {s: [] for s in ('train', 'validation', 'test')}
    for r in rows:
        role = assignment[r['subject']] if r['database'] == 'incartdb' else 'train'
        splits[role].append(r)
    old = json.loads((ROOT / 'data/cnn_mf_v1_protocol.json').read_text(encoding='utf-8'))
    for record in sorted(sum(old['records'].values(), [])):
        splits['train'].append({'database': 'mitdb', 'record': record,
                                'subject': 'mit:' + old['subject_alias'].get(record, record),
                                'lead': 'MLII', 'fs': 360})
    validate_splits(splits)
    prior = json.loads((ROOT / 'data/cnn_context_v4_protocol.json').read_text())
    p = {'version': 'cnn_expanded_v6_20261017', 'classes': list(LABELS), 'label_symbols': LABELS,
         'splits': splits, 'split_design': design, 'metadata_sha256': hashes,
         'metadata_only_selection': True,
         'identity_policy': 'INCART official patient IDs grouped across all I files; MIT201/202 alias (only202 included). SVDB patient identities unproven: single conservative group, train-only, never counted as78 subjects. Independent new validation/test exclusively INCART patients; provenance differs from MIT/SVDB, cross-database identity cannot be proved from deidentified records.',
         'old_data_policy': 'All42 old MIT records demoted to known development training in this new version, including old validation/test already inspected; old protocols/results preserved unchanged. New scores not comparable as same benchmark.',
         'window': {'before_seconds': 128/360, 'after_seconds': 192/360,
                    'target_hz': 144, 'output_samples': 128, 'std_floor_mv': .05,
                    'method': 'native crop ceil(fs*before/after); segment-local polyphase resample to144Hz with constant boundary; interpolate onto exact common time grid; mean/std per beat. No whole-record fit. Expert annotations; INCART timing not manually corrected. No fitted time offset.'},
         'train_sampling': {'seed': 2026101706, 'per_verified_subject_per_class': [500, 1500, 1500, 1500],
                            'svdb_per_record_per_class': [200, 300, 300, 300],
                            'selection': 'deterministic hash smallest; train-only cap, never validation/test; SVDB record unit is not a verified subject'},
         'rr': {'features': ['preRR/past80mean', 'preRR/past400mean', 'past80mean/past400mean'],
                'startup': 'past means exclude current; empty past uses current', 'clip': [0, 4], 'divide': 4, 'post_rr': False},
         'gate': prior['gate'], 'training': dict(prior['training'], max_epochs=50, minimum_epochs=20, patience=10, seed=2026101706),
         'candidates': [dict(prior['candidates'][1], id='expanded_residual_both16_aug'),
                        dict(prior['candidates'][2], id='expanded_mf_both24_aug')],
         'test_policy': 'Freeze before waveforms. Train and select all candidates by new validation only; save selection first, then one evaluation of selected model on new test. Once viewed this test becomes known; do not tune on its scores.',
         'scope': 'expert-centered cross-patient external-domain classification; not auto-QRS, INT8, FPGA or clinical validation',
         'smoke_board_test': 'NOT_TESTED',
         'sources': ['https://physionet.org/content/incartdb/1.0.0/', 'https://physionet.org/content/svdb/1.0.0/'],
         'data_license': 'INCART and SVDB ODC Attribution v1.0; raw data remains tmp; retain source attribution'}
    save(output, p)
    print(json.dumps({'protocol': str(output), 'sha256': digest(output), 'assignment': assignment}, ensure_ascii=False), flush=True)


@lru_cache(maxsize=8)
def resampling_filter(fs, target):
    # 与SciPy resample_poly默认Kaiser(5)设计相同，仅缓存系数避免每拍重设计。
    divisor=math.gcd(fs,target)
    rate=max(fs//divisor,target//divisor)
    return firwin(20*rate+1,1/rate,window=('kaiser',5.0))


def common_window(signal, index, fs, cfg):
    before = math.ceil(fs * cfg['before_seconds'])
    after = math.ceil(fs * cfg['after_seconds'])
    if index < before or index + after > len(signal):
        return None
    fs = int(fs)
    factor = math.gcd(fs, cfg['target_hz'])
    sampled = resample_poly(signal[index-before:index+after], cfg['target_hz']//factor, fs//factor,
                            window=resampling_filter(fs,cfg['target_hz']),padtype='constant')
    origin = -before/fs
    times = np.arange(len(sampled))/cfg['target_hz'] + origin
    target = np.arange(cfg['output_samples'])/cfg['target_hz'] - cfg['before_seconds']
    if target[0] < times[0]-1e-10 or target[-1] > times[-1]+1e-10:
        raise ValueError('重采样网格外插')
    window = np.interp(target, times, sampled)
    window -= window.mean()
    return (window / max(float(window.std()), cfg['std_floor_mv'])).astype(np.float32)


def causal_rr(history):
    current = history[-1]
    past = history[:-1]
    local = np.mean(past[-80:]) if past else current
    global_ = np.mean(past[-400:]) if past else current
    return np.clip([current/local, current/global_, local/global_], 0, 4).astype(np.float32)/4


def prepare(raw, mit_raw, protocol, output):
    if output.exists():
        raise FileExistsError('不覆盖缓存')
    p = json.loads(protocol.read_text(encoding='utf-8'))
    validate_splits(p['splits'])
    output.mkdir(parents=True)
    shutil.copyfile(protocol, output/'protocol.json')
    mapping = {s: i for i, symbols in enumerate(p['label_symbols'].values()) for s in symbols}
    manifest = {'protocol_sha256': digest(protocol), 'input_samples': 128, 'source_data_sha256': {}, 'data': {},
                'environment': {'numpy': np.__version__, 'scipy': scipy.__version__, 'wfdb': wfdb.__version__}}
    for role, records in p['splits'].items():
        values = defaultdict(list)
        excluded = Counter()
        per_record = {}
        for row in records:
            directory = mit_raw if row['database'] == 'mitdb' else raw/row['database']
            record = row['record']; key = row['database'] + ':' + record
            official = checksum_map((directory/'SHA256SUMS.txt').read_bytes())
            hashes = {}
            for ext in ('dat', 'hea', 'atr'):
                path = directory/(record+'.'+ext)
                hashes[ext] = digest(path)
                if hashes[ext] != official[path.name]:
                    raise ValueError('原始文件SHA不符：' + str(path))
                meta_key = row['database']+'/'+path.name
                if ext != 'dat' and meta_key in p['metadata_sha256'] and hashes[ext] != p['metadata_sha256'][meta_key]:
                    raise ValueError('冻结后标注变化')
            manifest['source_data_sha256'][key] = hashes
            h = wfdb.rdheader(str(directory/record)); channel = h.sig_name.index(row['lead'])
            if h.fs != row['fs'] or h.units[channel] != 'mV':
                raise ValueError('采样率或幅值单位与协议不符')
            digital = wfdb.rdrecord(str(directory/record), channels=[channel], physical=False)
            d = digital.d_signal[:, 0]
            # 官方文件SHA之外，独立核对WFDB首值/16位模和；不检查未使用的导联。
            if int(d[0]) != h.init_value[channel] or (int(d.astype(np.int64).sum())-h.checksum[channel]) % 65536:
                raise ValueError('WFDB首值/校验和错误：' + key)
            physical = (d.astype(np.float64)-h.baseline[channel])/h.adc_gain[channel]
            if not np.isfinite(physical).all():
                raise ValueError('非有限波形')
            ann = wfdb.rdann(str(directory/record), 'atr')
            previous = None; history = []; count = Counter()
            for index, symbol in zip(ann.sample, ann.symbol):
                index = int(index)
                if symbol not in BEATS:
                    continue
                if previous is None:
                    previous = index; excluded['first_beat_no_rr'] += 1; continue
                delta = index-previous; previous = index
                if delta <= 0:
                    raise ValueError('非正RR')
                history.append(delta/row['fs'])
                if symbol not in mapping:
                    excluded['unmapped_'+symbol] += 1; continue
                window = common_window(physical, index, row['fs'], p['window'])
                if window is None:
                    excluded['incomplete_window'] += 1; continue
                sample = {'x': window, 'rr': causal_rr(history), 'y': mapping[symbol], 'record': key,
                          'subject': row['subject'], 'r_index': index, 'code': symbol,
                          'sampling_unit': key if row['database']=='svdb' else row['subject']}
                for k, v in sample.items():
                    values[k].append(v)
                count[symbol] += 1
            per_record[key] = dict(count)
            print(json.dumps({'stage': 'prepare', 'role': role, 'record': key, 'counts': dict(count)}), flush=True)
        arrays = {k: np.asarray(v, dtype=np.float32 if k in ('x','rr') else (np.int64 if k in ('y','r_index') else None)) for k, v in values.items()}
        before = np.bincount(arrays['y'], minlength=4).tolist()
        if role == 'train':
            indices = []
            for unit in sorted(set(arrays['sampling_unit'])):
                caps = p['train_sampling']['svdb_per_record_per_class' if unit.startswith('svdb:') else 'per_verified_subject_per_class']
                for cls, cap in enumerate(caps):
                    ids = np.flatnonzero((arrays['sampling_unit']==unit) & (arrays['y']==cls))
                    ranked = sorted(ids, key=lambda i: hashlib.sha256(f"{p['train_sampling']['seed']}:{arrays['record'][i]}:{arrays['r_index'][i]}".encode()).digest())
                    indices.extend(ranked[:cap])
            take = np.array(sorted(indices))
            arrays = {k: v[take] for k, v in arrays.items()}
        counts = np.bincount(arrays['y'], minlength=4).tolist()
        if not all(counts):
            raise ValueError('缺目标类别；不自动删类')
        np.savez_compressed(output/(role+'.npz'), **arrays)
        manifest['data'][role] = {'examples': len(arrays['y']), 'class_counts': counts, 'before_train_cap': before,
                                  'class_verified_subject_counts': [len(set(arrays['subject'][(arrays['y']==i) & (arrays['subject']!='svdb:identity_unknown_pool')])) for i in range(4)],
                                  'excluded': dict(excluded), 'per_record_symbols_before_cap': per_record,
                                  'file_sha256': digest(output/(role+'.npz'))}
    manifest['source_sha256']={}
    for source in ('data/prepare_cnn_expanded.py','data/download_external_ecg.py'):
        manifest['source_sha256'][source]=digest(ROOT/source)
        dst=output/'source_snapshot'/source;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,dst)
    save(output/'manifest.json', manifest)
    print(json.dumps(manifest['data'],ensure_ascii=False),flush=True)


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('stage', choices=['freeze','prepare'])
    ap.add_argument('--raw-dir', type=Path, required=True)
    ap.add_argument('--mit-raw-dir', type=Path)
    ap.add_argument('--protocol', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path)
    args=ap.parse_args()
    if args.stage=='freeze':
        freeze(args.raw_dir, args.protocol)
    else:
        if args.output_dir is None or args.mit_raw_dir is None:
            ap.error('prepare需要mit-raw-dir与output-dir')
        prepare(args.raw_dir,args.mit_raw_dir,args.protocol,args.output_dir)
