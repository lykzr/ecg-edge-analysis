"""按当前工程标准重判历史开发成绩；不训练，不重写原始评价。"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def evaluate(root=ROOT):
    policy = json.loads((root / 'model/hgb_quality_policy.json').read_text(encoding='utf-8'))
    source = root / 'model/inference/evidence/evaluation_summary.json'
    mode = json.loads(source.read_text(encoding='utf-8'))['versions']['v92']['modes']['hp05']
    pooled = mode['pooled']
    checks = {}
    for i, label in enumerate(pooled['labels']):
        checks[label + '_precision'] = pooled['precision'][i] >= policy['minimum_precision']
        checks[label + '_recall'] = pooled['recall'][i] >= policy['minimum_recall']
    checks['macro_f1'] = pooled['macro_f1'] >= policy['minimum_macro_f1']
    original_f = mode['original'][3]
    checks['F_recall'] = original_f['positive'] / original_f['support'] >= policy['minimum_F_recall']
    checks['every_fold'] = all(
        fold['macro_f1'] >= policy['minimum_macro_f1']
        and all(v >= policy['minimum_precision'] for v in fold['precision'])
        and all(v >= policy['minimum_recall'] for v in fold['recall'])
        for fold in mode['folds'])
    # 原患者支持数口径不完整，未知项阻止整体通过，不能推测后补。
    checks['patient_precision_recall'] = None
    checks['minute_MAE'] = mode['minute_MAE'] <= policy['maximum_VF_minute_MAE']
    checks['worst_minute'] = abs(mode['worst_minute']['count_error']) <= policy['maximum_absolute_minute_error']
    checks['table_budget'] = mode['table_bytes24'] <= policy['maximum_table_bytes24']
    return dict(policy_version=policy['version'], source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                scope='既有v92 hp05三折开发评价重判；未重跑原始记录，非部署fold0独立测试',
                checks=checks, qualified=all(v is True for v in checks.values()), historical_gate_fields_ignored=True)


if __name__ == '__main__':
    result = evaluate()
    saved = json.loads((ROOT / 'docs/evidence/hgb_quality_90_20261101.json').read_text(encoding='utf-8'))
    assert result == saved, '新版门槛或原评价变化，须更新重判证据，不能沿用旧结论'
    print(json.dumps(dict(evidence_matches=True, **result), ensure_ascii=False))
