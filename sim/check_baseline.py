"""复核随源码交接的失败开发基线；不训练、不读取独立测试。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/baseline'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check(base=BASE, cache=None, replay_weights=False, metrics_only=False):
    base = Path(base).resolve()
    manifest = read(base / 'files.json')
    assert manifest['candidate'] == 'residual_verified' and not manifest['test_loaded']
    for name, row in manifest['files'].items():
        path = (base / name).resolve()
        path.relative_to(base)
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], name
    protocol = read(base / 'protocol.json')
    origin = read(base / 'manifest_start.json')
    assert digest(base / 'protocol.json') == origin['protocol_sha256']
    assert origin['test_access'] == 'NO_TEST_READER_IN_THIS_SCRIPT'
    for name, expected in origin['source_sha256'].items():
        assert digest(ROOT / name) == expected, name
    git_protocol_path = ROOT / manifest['source_protocol']
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
