"""只读导出冻结v92/fold0为C常量；无拟合，派生产物必须进入新目录。"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'model/inference'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(output):
    output = Path(output).resolve()
    profile = json.loads((MODULE / 'integration_profile.json').read_text(encoding='utf-8'))
    assert profile['fold'] == 0 and profile['model_version'] == 'v92'
    weight = MODULE / profile['model_file']
    assert sha(weight) == profile['model_sha256']
    assert sha(MODULE / 'config.json') == profile['config_sha256']
    with np.load(weight, allow_pickle=False) as model, np.load(MODULE / 'assets/hermite_basis.npz', allow_pickle=False) as hermite:
        assert int(model['input_features']) == 192 and int(model['max_depth']) == 5
        np.testing.assert_array_equal(model['classes'], [0, 1, 2])
        lines = ['/* 由build/export_hgb.py生成；原double参数不量化，不重新训练。 */', '#include "hgb.h"',
                 f'const char hgb_model_sha256[]="{sha(weight)}";',
                 f'const char hgb_config_sha256[]="{sha(MODULE / "config.json")}";',
                 'const HgbNode hgb_nodes[]={']
        offsets = [0]
        for stage in range(64):
            for label in range(3):
                nodes = model[f'tree_{stage}_{label}']
                assert not nodes['is_categorical'].any()
                for row in nodes:
                    leaf = int(row['is_leaf'])
                    left, right, feature = (int(row[k]) for k in ('left', 'right', 'feature_idx'))
                    if not leaf:
                        assert 0 <= feature < 192 and 0 <= left < len(nodes) and 0 <= right < len(nodes)
                    assert np.isfinite(row['value']) and np.isfinite(row['num_threshold'])
                    lines.append('{%s,%s,%d,%d,%d,%d},' % (float(row['value']).hex(), float(row['num_threshold']).hex(), left, right, feature, leaf))
                offsets.append(offsets[-1] + len(nodes))
        lines += ['};', 'const uint32_t hgb_tree_offsets[193]={' + ','.join(map(str, offsets)) + '};',
                  'const double hgb_baseline[3]={' + ','.join(float(v).hex() for v in model['baseline'].ravel()) + '};',
                  'const float hgb_hermite_basis[37][6]={']
        basis = hermite['basis'].astype(np.float32)
        assert basis.shape == (37, 6) and np.isfinite(basis).all()
        lines += ['{' + ','.join(float(v).hex() + 'f' for v in row) + '},' for row in basis]
        lines += ['};', '']
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'hgb_parameters.c'
    target.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    result = dict(model_sha256=sha(weight), config_sha256=sha(MODULE / 'config.json'),
                  basis_sha256=sha(MODULE / 'assets/hermite_basis.npz'),
                  generator_sha256=sha(Path(__file__)), generated_sha256=sha(target),
                  fold=0, trees=192, nodes=offsets[-1], fits=0, quantized=False,
                  source='model/inference', qualified=False)
    (output / 'parameters.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    print(json.dumps(export(parser.parse_args().output)))
