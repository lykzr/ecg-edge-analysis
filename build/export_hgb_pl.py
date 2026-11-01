"""导出冻结HGB到PL ROM及受控仿真向量；不训练，不改原始权重。"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
Q = 40


def key(x):
    x = np.float32(x)
    if x == 0:
        x = np.float32(0)
    u = int(x.view(np.uint32))
    return (~u & 0xffffffff) if u >> 31 else (u ^ 0x80000000)


def floor32(t):
    f = np.float32(t)
    if float(f) > t:
        f = np.nextafter(f, np.float32(-np.inf))
    return f


def export(output):
    output = Path(output).resolve()
    output.relative_to(ROOT / 'tmp')
    output.mkdir(parents=True, exist_ok=False)
    weight = ROOT / 'model/inference/assets/v92_fold0.npz'
    digest = hashlib.sha256(weight.read_bytes()).hexdigest()
    assert digest == '375cf45ac1f315ecc517a219cb03340727304db8e7738626ac4b4920a5af00f8'
    model = np.load(weight, allow_pickle=False)
    assert int(model['input_features']) == 192 and int(model['max_depth']) == 5
    baselines = [round(float(v) * 2**Q) for v in model['baseline'].ravel()]
    lanes, roots, headers = [], [], []
    boundary = []
    leaf_bound = []
    for c in range(3):
        rows, starts, bound = [], [], abs(baselines[c])
        for s in range(64):
            tree = model[f'tree_{s}_{c}']
            assert not tree['is_categorical'].any()
            first = len(rows)
            starts.append(first)
            bound += max(abs(round(float(n['value']) * 2**Q)) for n in tree if n['is_leaf'])
            for n in tree:
                leaf, feat = int(n['is_leaf']), int(n['feature_idx'])
                left, right = first + int(n['left']), first + int(n['right'])
                t = float(n['num_threshold'])
                v = round(float(n['value']) * 2**Q)
                assert np.isfinite(t) and abs(v) < 2**62
                cut = floor32(t)
                if not leaf:
                    assert 0 <= feat < 192
                    boundary.append((feat, cut))
                word = (leaf << 127) | (feat << 119) | (left << 107) | (right << 95) | (key(cut) << 63) | (v & ((1 << 63)-1))
                rows.append(word)
        assert len(rows) <= 4096 and bound < 2**63
        leaf_bound.append(bound)
        lanes.append(rows)
        roots.append(starts)
        (output / f'nodes_{c}.mem').write_text(''.join(f'{w:032x}\n' for w in rows) + '00000000000000000000000000000000\n' * (4096-len(rows)))
        (output / f'roots_{c}.mem').write_text(''.join(f'{w:03x}\n' for w in starts))
        headers.append(f"`define HGB_BASE_{c} 64'h{baselines[c] & ((1<<64)-1):016x}")
    (output / 'hgb_pl_config.vh').write_text('\n'.join(headers)+'\n')

    def run(x):
        scores, original = baselines.copy(), model['baseline'].ravel().copy()
        for s in range(64):
            for c in range(3):
                tree = model[f'tree_{s}_{c}']; at = 0
                while not tree[at]['is_leaf']:
                    n = tree[at]; f = x[int(n['feature_idx'])]
                    decision = float(f) <= float(n['num_threshold'])
                    assert decision == (key(f) <= key(floor32(float(n['num_threshold']))))
                    at = int(n['left'] if decision else n['right'])
                value = float(tree[at]['value'])
                scores[c] += round(value * 2**Q)
                original[c] += value
        return scores, original

    golden = np.load(ROOT / 'model/inference/examples/feature_vectors.npz')
    features = list(golden['features'])
    rng = np.random.default_rng(9210)
    features.extend(rng.normal(0, 5, (64,192)).astype(np.float32))
    features.extend([np.zeros(192,np.float32), np.full(192,-0.0,np.float32),
                     np.full(192,np.finfo(np.float32).max,np.float32),
                     np.full(192,-np.finfo(np.float32).max,np.float32)])
    # 每个分裂点两侧的独立输入检验浮点比较的精确边界转换。
    for feat, cut in boundary:
        for f in (cut, np.nextafter(cut,np.float32(np.inf))):
            if np.isfinite(f):
                assert (float(f) <= float(cut)) == (key(f) <= key(cut))
    for feat, cut in boundary[::32]:
        for f in (cut, np.nextafter(cut,np.float32(np.inf))):
            x = np.zeros(192,np.float32);x[feat]=f;features.append(x)
    features = np.asarray(features,np.float32)
    expected, max_error, changed = [], 0., 0
    for i,x in enumerate(features):
        scores,original=run(x);expected.append(scores)
        p=np.exp(np.asarray(scores)/2**Q-max(scores)/2**Q);p/=p.sum()
        ref=np.exp(original-original.max());ref/=ref.sum()
        max_error=max(max_error,float(np.max(np.abs(p-ref))))
        changed += int(np.argmax(scores)!=np.argmax(original))
        if i < 160:np.testing.assert_allclose(ref,golden['probability_fold_0'][i],atol=2e-14,rtol=0)
    assert changed == 0
    (output/'features.mem').write_text(''.join(f'{int(u):08x}\n' for u in features.view(np.uint32).ravel()))
    (output/'scores.mem').write_text(''.join(f'{v & ((1<<64)-1):016x}\n' for row in expected for v in row))
    (output/'vectors.vh').write_text(f'`define HGB_TEST_COUNT {len(features)}\n')
    # 相同精度ARM基线：直接使用同一份ROM参数，禁止拿原double基线混称同精度。
    c=['#include <stdint.h>', '#include "hgb_pl_fixture.h"',
       'const int64_t hgb_qbaseline[3]={'+','.join(str(x)+'LL' for x in baselines)+'};',
       'const HgbQNode hgb_qnodes[3][4096]={']
    for rows in lanes:
        c.append('{')
        for w in rows:
            value=w & ((1<<63)-1)
            if value & (1<<62):value-=1<<63
            c.append('{%dLL,0x%08xU,%d,%d,%d,%d},' % (value,(w>>63)&0xffffffff,(w>>107)&4095,(w>>95)&4095,(w>>119)&255,(w>>127)&1))
        c.append('},')
    c+=['};','const uint16_t hgb_qroots[3][64]={']
    c+=['{'+','.join(map(str,r))+'},' for r in roots]
    c+=['};','const uint32_t hgb_test_features[160][192]={']
    c+=['{'+','.join(f'0x{int(u):08x}U' for u in x.view(np.uint32))+'},' for x in features[:160]]
    c+=['};','const int64_t hgb_test_scores[160][3]={']
    c+=['{'+','.join(str(v)+'LL' for v in row)+'},' for row in expected[:160]]
    c+=['};']
    (output/'hgb_pl_fixture.c').write_text('\n'.join(c)+'\n')
    (output/'hgb_pl_fixture.h').write_text('''#include <stdint.h>
typedef struct {int64_t value;uint32_t threshold;uint16_t left,right;uint8_t feature,leaf;} HgbQNode;
extern const int64_t hgb_qbaseline[3];
extern const HgbQNode hgb_qnodes[3][4096];
extern const uint16_t hgb_qroots[3][64];
extern const uint32_t hgb_test_features[160][192];
extern const int64_t hgb_test_scores[160][3];
''')
    result=dict(model_sha256=digest,trees=192,nodes=[len(x) for x in lanes],fraction_bits=Q,
                baseline_q40=baselines,accumulator_abs_bound=leaf_bound,vectors=len(features),
                max_probability_error=max_error,class_changes=changed,qualified=False,
                score_error_bound=65*0.5/2**Q,threshold='float32 floor + ordered IEEE754, finite input only',
                arithmetic='signed 64-bit Q40 sums; round ties-to-even at export; no saturation',
                files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()})
    (output/'export.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True)
    print(json.dumps(export(ap.parse_args().output)))
