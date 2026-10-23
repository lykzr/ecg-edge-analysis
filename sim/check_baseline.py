"""复核随源码交接的失败开发基线；不训练、不读取独立测试。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from check_checkout import manifest_path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'model/baseline'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def source_path(name):
    """把冻结基线里记录的旧 data/ 路径映射到 2026-10-23 迁入 model/ 的位置。"""
    manifest_path(ROOT, name)  # 先拒绝绝对路径、盘符及目录逃逸。
    name = name.replace('\\', '/')
    if name.startswith('data/cnn_'):
        return ROOT / 'model/protocols' / Path(name).name
    if name.startswith('data/prepare_cnn') or name.startswith('data/extend_cnn') \
            or name.startswith('data/download_external') or name.startswith('data/profile_classification'):
        return ROOT / 'model/prepare' / Path(name).name
    if name.startswith('data/train_cnn'):
        # 基线冻结时记录的是迁移前脚本哈希，验旧快照；当前训练入口由 check_training_checkout 核验。
        return ROOT / 'model/baseline/legacy_sources' / Path(name).name
    if name.startswith('data/baseline/'):
        return ROOT / 'model/baseline' / Path(name).relative_to('data/baseline')
    if name.startswith('data/requirements_cnn'):
        return ROOT / 'model' / Path(name).name
    return ROOT / name


def check(base=BASE, cache=None, replay_weights=False, metrics_only=False):
    base = Path(base).resolve()
    manifest = read(base / 'files.json')
    assert manifest['candidate'] == 'residual_verified' and not manifest['test_loaded']
    for name, row in manifest['files'].items():
        path = manifest_path(base, name)
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], name
    protocol = read(base / 'protocol.json')
    origin = read(base / 'manifest_start.json')
    assert digest(base / 'protocol.json') == origin['protocol_sha256']
    assert origin['test_access'] == 'NO_TEST_READER_IN_THIS_SCRIPT'
    for name, expected in origin['source_sha256'].items():
        assert digest(source_path(name)) == expected, name
    git_protocol_path = source_path(manifest['source_protocol'])
    assert digest(git_protocol_path) == manifest['source_protocol_sha256']
    git_protocol = read(git_protocol_path)
    assert git_protocol['folds'] == protocol['folds']
    assert git_protocol['excluded_independent_test_subjects'] == protocol['excluded_independent_test_subjects']
    decision = read(base / 'decision.json')
    selected = decision['selected']
    assert selected['config']['id'] == manifest['candidate'] and not decision['accepted']
    result = {'passed': True, 'file_count': len(manifest['files']),
              'model_accepted': False, 'test_loaded': False, 'weights_replayed': False,
              'scope': 'previously observed development baseline only, not final model or independent test'}
    if not (metrics_only or cache or replay_weights):
        return result
    if replay_weights and cache is None:
        raise ValueError('--replay-weights需要--cache-dir，数据按Git入口重建')
    import numpy as np
    from verify_cnn_cv import metrics, compare, accepted, replay
    dev = None
    if cache is not None:
        sys.path.insert(0, str(ROOT / 'model/prepare'))
        sys.path.insert(0, str(ROOT / 'data'))
        from prepare_cnn_git import array_digest
        dev = dict(np.load(Path(cache) / 'development.npz', allow_pickle=False))
        assert {k: array_digest(v) for k, v in dev.items()} == git_protocol['expected_array_sha256']['development']
        assert not set(dev['subject']) & set(protocol['excluded_independent_test_subjects'])
    joined = []; scores = []
    for fold, subjects in enumerate(protocol['folds']):
        folder = base / 'residual_verified' / f'fold_{fold}'
        saved = dict(np.load(folder / 'validation_predictions.npz', allow_pickle=False))
        assert set(saved['subject']) == set(subjects)
        computed = metrics(saved['true'], saved['prediction'])
        compare(read(folder / 'validation_metrics.json'), computed)
        for subject in subjects:
            mask = saved['subject'] == subject
            compare(read(folder / 'validation_metrics.json')['per_subject'][subject], metrics(saved['true'][mask], saved['prediction'][mask]))
        recorded = read(folder / 'result.json')
        assert digest(folder / 'best_weights.pt') == recorded['weights_sha256']
        assert not set(recorded['train_subjects']) & (set(subjects) | set(protocol['excluded_independent_test_subjects']))
        assert recorded['validation_gate']['passed'] == accepted(computed, recorded['resources']['trainable_parameters'], protocol['gate'])
        if dev is not None:
            ids = np.flatnonzero(np.isin(dev['subject'], subjects))
            for key in ('subject', 'record', 'r_index'):
                np.testing.assert_array_equal(saved[key], dev[key][ids])
            np.testing.assert_array_equal(saved['true'], dev['y'][ids])
            if replay_weights:
                predicted, count = replay(folder, selected['config'], dev, ids, read(folder / 'normalization.json'))
                np.testing.assert_array_equal(predicted, saved['prediction'])
                assert count == recorded['resources']['trainable_parameters']
        scores.append(computed['macro_f1']); joined.append(saved)
    pooled = dict(np.load(base / 'residual_verified/oof_predictions.npz', allow_pickle=False))
    for key in pooled:
        np.testing.assert_array_equal(pooled[key], np.concatenate([v[key] for v in joined]))
    computed = metrics(pooled['true'], pooled['prediction'])
    compare(read(base / 'residual_verified/oof_metrics.json'), computed)
    compare(selected['oof_metrics'], computed)
    assert abs(sum(scores) / len(scores) - selected['mean_fold_macro_f1']) < 1e-12
    return dict(result, metrics_recomputed=True, weights_replayed=replay_weights,
                examples=len(pooled['true']), mean_fold_macro_f1=sum(scores) / len(scores),
                pooled_macro_f1=computed['macro_f1'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--metrics', action='store_true')
    parser.add_argument('--replay-weights', action='store_true')
    args = parser.parse_args()
    if args.replay_weights:
        import torch
        torch.set_num_threads(2)
    print(json.dumps(check(cache=args.cache_dir, replay_weights=args.replay_weights,
                           metrics_only=args.metrics), ensure_ascii=False))
