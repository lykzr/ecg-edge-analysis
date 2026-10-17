"""独立复算患者CV预测、门槛、来源隔离与哈希，可选从权重重放全部验证拍。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def metrics(y, prediction):
    if y.shape != prediction.shape or np.any((y < 0) | (y > 3)) or np.any((prediction < 0) | (prediction > 3)):
        raise ValueError('标签/预测越界或形状不一致')
    cm = np.zeros((4, 4), dtype=np.int64)
    np.add.at(cm, (y, prediction), 1)
    support = cm.sum(1)
    precision = np.diag(cm) / np.maximum(cm.sum(0), 1)
    recall = np.diag(cm) / np.maximum(support, 1)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-30)
    return {'confusion_matrix_rows_true': cm.tolist(), 'support': support.tolist(),
            'precision': precision.tolist(), 'recall': recall.tolist(), 'f1': f1.tolist(),
            'macro_f1': float(f1.mean()), 'accuracy': float(np.trace(cm) / max(len(y), 1))}


def compare(actual, expected):
    for name, values in expected.items():
        np.testing.assert_allclose(actual[name], values, rtol=0, atol=1e-12, err_msg=name)


def accepted(metric, parameters, limits):
    return bool(metric['macro_f1'] >= limits['macro_f1']
                and min(metric['f1']) >= limits['minimum_class_f1']
                and np.all(np.array(metric['recall']) >= limits['recall'])
                and parameters <= limits['maximum_parameters'])


def training_indices(dev, aux, held, config, protocol):
    # 独立按冻结采样定义重建训练索引，不调用训练脚本的 split_arrays。
    selected = []
    seed = protocol['train_sampling']['seed']
    for subject in sorted(set(dev['subject']) - set(held)):
        for cls, cap in enumerate(protocol['train_sampling']['per_verified_subject_per_class']):
            ids = np.flatnonzero((dev['subject'] == subject) & (dev['y'] == cls))
            ids = sorted(ids, key=lambda i: hashlib.sha256(
                f"{seed}:{dev['record'][i]}:{dev['r_index'][i]}".encode()).digest())
            selected.extend(ids[:cap])
    selected = np.array(sorted(selected), dtype=np.int64)
    auxiliary = np.arange(len(aux['y'])) if config['sources'] == 'all' else np.flatnonzero(
        np.char.startswith(aux['record'], 'mitdb:'))
    return selected, auxiliary


def replay(folder, config, dev, indices, normalization):
    import torch
    from torch import nn
    sys.path.insert(0, str(ROOT / 'src/reference'))
    from ecg_temporal_cnn import TemporalCnn
    from ecg_trainable_cnn import create_model
    if config['family'] == 'temporal':
        model = TemporalCnn(16)
    else:
        model = create_model({'family': 'residual', 'feature': 'both', 'width': 16, 'input_samples': 128})
        def remove_bn(module):
            for name, child in list(module.named_children()):
                if isinstance(child, nn.BatchNorm1d):
                    setattr(module, name, nn.Identity())
                else:
                    remove_bn(child)
        remove_bn(model)
    model.load_state_dict(torch.load(folder / 'best_weights.pt', weights_only=True))
    model.eval()
    rr = torch.from_numpy(dev['rr'][indices])
    rr = ((rr - torch.tensor(normalization['rr_mean'])) / torch.tensor(normalization['rr_std'])).clamp(-5, 5)
    x = torch.from_numpy(dev['x'][indices])
    outputs = []
    with torch.no_grad():
        for start in range(0, len(indices), 1024):
            outputs.append(model(x[start:start + 1024], rr[start:start + 1024]).argmax(1).numpy())
    return np.concatenate(outputs), sum(p.numel() for p in model.parameters())


def verify(cache, run, replay_weights=False):
    protocol = read(run / 'protocol.json')
    start = read(run / 'manifest_start.json')
    manifest = read(cache / 'manifest.json')
    decision = read(run / 'decision.json')  # 未完成轮次不能冒充最终复核。
    assert digest(run / 'protocol.json') == start['protocol_sha256'] == manifest['protocol_sha256']
    assert digest(cache / 'manifest.json') == start['cache_manifest_sha256']
    assert start['test_access'] == 'NO_TEST_READER_IN_THIS_SCRIPT'
    assert decision['test_status'] == 'NOT_LOADED'
    assert decision['smoke_board_test'] == 'NOT_TESTED'
    for name, expected in start['source_sha256'].items():
        assert digest(ROOT / name) == digest(run / 'source_snapshot' / name) == expected, name
    for name in ('development', 'auxiliary'):
        assert digest(cache / (name + '.npz')) == manifest[name + '_sha256']
    dev = dict(np.load(cache / 'development.npz', allow_pickle=False))
    aux = dict(np.load(cache / 'auxiliary.npz', allow_pickle=False))
    excluded = set(protocol['excluded_independent_test_subjects'])
    folds = [s for fold in protocol['folds'] for s in fold]
    assert len(folds) == len(set(folds)) and not set(folds) & excluded
    assert set(dev['subject']) == set(folds)
    assert not (set(dev['subject']) | set(aux['subject'])) & excluded
    summaries = read(run / 'candidate_summary.json')
    assert [s['config'] for s in summaries] == protocol['candidates']
    epochs = 0
    evidence = []
    for summary in summaries:
        config = summary['config']
        candidate = run / config['id']
        fold_metrics = []
        prediction_sets = []
        fold_losses = []
        fold_passed = []
        for fold, held in enumerate(protocol['folds']):
            folder = candidate / f'fold_{fold}'
            result = read(folder / 'result.json')
            saved = dict(np.load(folder / 'validation_predictions.npz', allow_pickle=False))
            ids = np.flatnonzero(np.isin(dev['subject'], held))
            for name in ('subject', 'record', 'r_index'):
                np.testing.assert_array_equal(saved[name], dev[name][ids])
            np.testing.assert_array_equal(saved['true'], dev['y'][ids])
            recalculated = metrics(saved['true'], saved['prediction'])
            recorded = read(folder / 'validation_metrics.json')
            compare(recorded, recalculated)
            for subject in held:
                mask = saved['subject'] == subject
                compare(recorded['per_subject'][subject], metrics(saved['true'][mask], saved['prediction'][mask]))
            assert abs(result['validation_macro_f1'] - recalculated['macro_f1']) < 1e-12
            history = [json.loads(line) for line in (folder / 'epochs.jsonl').read_text(encoding='utf-8').splitlines()]
            assert len(history) == result['epochs']
            assert history[result['best_epoch'] - 1]['validation_macro_f1'] == result['validation_macro_f1']
            assert not any(row['validation_macro_f1'] > result['validation_macro_f1'] + 1e-8 for row in history)
            assert digest(folder / 'best_weights.pt') == result['weights_sha256']
            assert set(result['validation_subjects']) == set(held)
            assert not set(result['train_subjects']) & (set(held) | excluded)
            selected, auxiliary = training_indices(dev, aux, held, config, protocol)
            labels = np.concatenate([dev['y'][selected], aux['y'][auxiliary]])
            assert result['train_counts'] == np.bincount(labels, minlength=4).tolist()
            rr = np.concatenate([dev['rr'][selected], aux['rr'][auxiliary]])
            norm = read(folder / 'normalization.json')
            # torch与NumPy并行规约浮点次序不同；float64独立统计仅用小容差核对。
            np.testing.assert_allclose(norm['rr_mean'], rr.astype(np.float64).mean(0), atol=2e-6, rtol=1e-5)
            np.testing.assert_allclose(norm['rr_std'], np.maximum(rr.astype(np.float64).std(0), .01), atol=2e-6, rtol=1e-5)
            assert norm['fitted_role'] == 'fold_train'
            if replay_weights:
                predicted, count = replay(folder, config, dev, ids, norm)
                np.testing.assert_array_equal(predicted, saved['prediction'])
                assert count == result['resources']['trainable_parameters']
            passed = accepted(recalculated, result['resources']['trainable_parameters'], protocol['gate'])
            assert passed == result['validation_gate']['passed']
            epochs += result['epochs']
            fold_passed.append(passed)
            fold_metrics.append(recalculated['macro_f1'])
            fold_losses.append(result['validation_loss'])
            prediction_sets.append(saved)
        joined = {k: np.concatenate([v[k] for v in prediction_sets]) for k in prediction_sets[0]}
        pooled = dict(np.load(candidate / 'oof_predictions.npz', allow_pickle=False))
        for name in pooled:
            np.testing.assert_array_equal(pooled[name], joined[name])
        identities = set(zip(pooled['record'].tolist(), pooled['r_index'].tolist()))
        expected_ids = set(zip(dev['record'].tolist(), dev['r_index'].tolist()))
        assert len(pooled['true']) == len(identities) == len(dev['y']) and identities == expected_ids
        recalculated = metrics(pooled['true'], pooled['prediction'])
        compare(read(candidate / 'oof_metrics.json'), recalculated)
        compare(summary['oof_metrics'], recalculated)
        np.testing.assert_allclose(summary['fold_macro_f1'], fold_metrics, rtol=0, atol=1e-12)
        assert abs(summary['mean_fold_macro_f1'] - np.mean(fold_metrics)) < 1e-12
        assert abs(summary['mean_fold_loss'] - np.mean(fold_losses)) < 1e-12
        pooled_passed = accepted(recalculated, summary['resources']['trainable_parameters'], protocol['gate'])
        assert summary['pooled_gate']['passed'] == pooled_passed
        passed = pooled_passed and all(fold_passed)
        assert summary['accepted'] == passed
        evidence.append({'candidate': config['id'], 'metrics': recalculated, 'accepted': passed,
                         'oof_predictions_sha256': digest(candidate / 'oof_predictions.npz')})
    selected = max(summaries, key=lambda s: (s['mean_fold_macro_f1'], -s['mean_fold_loss']))
    assert decision['selected'] == selected and decision['accepted'] == selected['accepted']
    assert decision['epochs'] == epochs
    assert not any('test_opened' in p.name or 'test_predictions' in p.name for p in run.rglob('*'))
    return {'verified': True, 'fold_fits': len(summaries) * 3, 'epochs': epochs,
            'weights_replayed': replay_weights, 'test_loaded': False, 'evidence': evidence,
            'decision_sha256': digest(run / 'decision.json'),
            'verifier_sha256': digest(Path(__file__)), 'smoke_board_test': 'NOT_TESTED'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay-weights', action='store_true')
    args = parser.parse_args()
    args.output.resolve().relative_to(ROOT / 'tmp')
    if args.output.exists():
        raise FileExistsError('不覆盖已有复核证据')
    if args.replay_weights:
        import torch
        torch.set_num_threads(2)
    outcome = verify(args.cache_dir, args.run_dir, args.replay_weights)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in outcome.items() if k != 'evidence'}, ensure_ascii=False))
