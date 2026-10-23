"""只检查Git交接源码完整性与协议隔离；不需要数据、PyTorch或本机tmp。"""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['model/prepare/prepare_cnn_git.py', 'model/protocols/cnn_git_v1_protocol.json', 'model/train/train_cnn_cv.py',
            'model/train/train_cnn_candidates.py', 'model/train/train_cnn_refined.py', 'model/prepare/prepare_cnn_expanded.py',
            'model/prepare/download_external_ecg.py', 'model/requirements_cnn_data.txt', 'model/requirements_cnn.txt',
            'src/reference/ecg_trainable_cnn.py', 'src/reference/ecg_temporal_cnn.py',
            'src/reference/ecg_mf_cnn.py', 'sim/verify_cnn_cv.py', 'sim/test_cnn_git.py',
            'docs/model_training_handoff.md', 'third_party.md', 'LICENSE']


def check(root=ROOT):
    missing = [f for f in REQUIRED if not (root / f).is_file()]
    if missing:
        raise FileNotFoundError('交接缺文件：' + ', '.join(missing))
    for file in REQUIRED:
        if file.endswith('.py'):
            ast.parse((root / file).read_text(encoding='utf-8-sig'))
    p = json.loads((root / 'model/protocols/cnn_git_v1_protocol.json').read_text(encoding='utf-8'))
    rows = p['development_records'] + p['auxiliary_records']
    assert not set(p['excluded_independent_test_subjects']) & {r['subject'] for r in rows}
    assert len(p['raw_sha256']) == 3 * len(rows)
    assert p['candidates'] == [{'id': 'residual_verified', 'family': 'residual', 'sources': 'verified'}]
    # 不导入Torch也可证明全部直接本地训练依赖已在清单中。
    stems = {Path(f).stem for f in REQUIRED}
    for file in ('model/train/train_cnn_cv.py', 'model/train/train_cnn_candidates.py', 'model/train/train_cnn_refined.py'):
        tree = ast.parse((root / file).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and (node.module.startswith('ecg_') or node.module.startswith('train_cnn_')):
                assert node.module in stems, node.module
    return {'passed': True, 'required_files': REQUIRED, 'requires_existing_tmp': False,
            'independent_test_records_included': False}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False))
