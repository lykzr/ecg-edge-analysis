"""新旧INT8核逐位对照；独立Python整数参考，非板测/准确率统计。"""
import argparse
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.cnn_fourclass.network import load_model, hand_features
from model.cnn_fourclass.int8_reference import Int8Reference


def check(parameters, output, compiler):
    parameters = Path(parameters).resolve()
    output = Path(output).resolve()
    output.relative_to(ROOT / 'tmp')
    output.mkdir(parents=True, exist_ok=False)
    funcs = []
    sources = [ROOT / f'src/hls/{name}/cnn_int8_hls.cpp' for name in ('ecg_cnn_int8', 'ecg_cnn_int8_fast')]
    sources.append(ROOT / 'src/hls/ecg_cnn_int8_fast/cnn_int8_conv16.cpp')
    environment = dict(os.environ, TMP=str(output), TEMP=str(output))
    for index, source in enumerate(sources):
        dll = output / f'network_{index}.dll'
        command = [compiler, '-shared', '-O2', '-ffp-contract=off', '-fno-fast-math',
                   '-Wno-unknown-pragmas', '-I', str(parameters), str(source), '-o', str(dll)]
        result = subprocess.run(command, capture_output=True, env=environment, timeout=120)
        (output / f'compile_{index}.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'编译失败：{output}')
        library = ct.CDLL(str(dll))
        func = library.cnn_int8_hls
        func.argtypes = [ct.POINTER(ct.c_float), ct.POINTER(ct.c_float)]
        func.restype = None
        funcs.append(func)
    z = np.load(ROOT / 'model/cnn_fourclass/assets/golden_0.npz', allow_pickle=False)
    golden = np.concatenate([z['x'], z['rr'], hand_features(z['x'], z['rr'], z['background'], z['history_count']), z['history_rr']], 1).astype('f4')
    rng = np.random.default_rng(20261104)
    random = rng.normal(size=(200, 261)).astype('f4')
    random[:, 128:131] = rng.uniform(.25, 2, (200, 3))
    # 动态量化的量级边界；不以任意NaN/溢出输入扩展原接口范围。
    scaled = np.concatenate([random[:4] * v for v in (2**-20, .125, 8., 1024.)])
    vectors = np.concatenate([golden, random, np.zeros((1, 261), 'f4'), np.ones((1, 261), 'f4'), scaled])
    reference = Int8Reference({k: v.numpy() for k, v in load_model(0).state_dict().items()})
    for vector in vectors:
        actual = []
        for func in funcs:
            y = np.empty(4, 'f4')
            func(vector.ctypes.data_as(ct.POINTER(ct.c_float)), y.ctypes.data_as(ct.POINTER(ct.c_float)))
            assert np.isfinite(y).all()
            actual.append(y)
        np.testing.assert_array_equal(actual[0].view('u4'), actual[1].view('u4'))
        np.testing.assert_array_equal(actual[0].view('u4'), actual[2].view('u4'))
        expected = reference.forward(vector)
        np.testing.assert_array_equal(actual[1].view('u4'), expected.view('u4'))
    summary = dict(passed=True, vectors=len(vectors), seed=20261104, bit_exact_old_new_and_python=True,
                   training=False, board=False, accuracy_measured=False,
                   scope='same INT8 model; does not remove existing INT8 versus FP32 quantization error',
                   sources={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                   fast_core_sha256=hashlib.sha256((ROOT / 'src/hls/ecg_cnn_int8_fast/int8_fast_core.h').read_bytes()).hexdigest())
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('parameters', 'output', 'cxx'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    check(args.parameters, args.output, args.cxx)
