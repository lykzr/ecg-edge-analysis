"""将实际USB_UART返回与冻结模型整段参考比较，不给患者准确率结论。"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'model/inference'))
from ecg_model.pipeline import infer_mv
from ecg_model.tree_model import probability


def verify(directory, input_mv):
    directory = Path(directory).resolve()
    input_mv = Path(input_mv).resolve()
    receipt = json.loads((directory / 'input.json').read_text())
    assert hashlib.sha256(input_mv.read_bytes()).hexdigest() == receipt['sha256']
    actual = json.loads((directory / 'result.json').read_text())
    model = ROOT / 'model/inference/assets/v92_fold0.npz'
    assert hashlib.sha256(model.read_bytes()).hexdigest() == actual['model_sha256']
    signal = np.loadtxt(input_mv, delimiter=',')
    reference = infer_mv(signal, fold=0, preprocess=actual['preprocess'])
    requests = reference['requests']
    sys.path.insert(0, str(ROOT / 'sim'))
    from check_hgb_arm import reference as context_reference
    features, decisions, _ = context_reference(requests, len(signal))
    valid = requests['input_status'] == 0
    expected = np.full((len(requests), 3), np.nan)
    with np.load(model, allow_pickle=False) as weights:
        expected[valid] = probability(features[valid], weights)
    rows = actual['events']
    assert actual['passed'] and actual['samples'] == len(signal) and len(rows) == len(requests)
    for key in ('beat_id', 'position', 'ready_at'):
        np.testing.assert_array_equal([v[key] for v in rows], requests[key])
    np.testing.assert_array_equal([v['status'] for v in rows], requests['input_status'])
    np.testing.assert_array_equal([v['decision_at'] for v in rows], decisions)
    classes = np.full(len(rows), -1, dtype=np.int32)
    classes[valid] = expected[valid].argmax(axis=1)
    np.testing.assert_array_equal([v['class_id'] for v in rows], classes)
    p = np.asarray([[np.nan if x is None else x for x in v['probability']] for v in rows])
    np.testing.assert_allclose(p, expected, rtol=1e-10, atol=1e-10, equal_nan=True)
    result = dict(passed=True, physical_arm_uart=True, samples=len(signal), events=len(rows),
                  valid=int(valid.sum()), probability_max_abs=float(np.max(abs(p[valid]-expected[valid]))) if valid.any() else 0,
                  positions_status_classes_decisions_equal=True, compute_us=actual['compute_us'],
                  scope='controlled full-record ARM UART; not wireless, patient accuracy or rolling inference',
                  files={name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
                         for name in ('input.json', 'result.json', 'rx.log', 'tx.bin')})
    (directory/'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--input-mv', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, args.input_mv), ensure_ascii=False))
