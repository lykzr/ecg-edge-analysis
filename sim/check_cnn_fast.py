"""原FP32 HLS与四输出候选的独立原生编译对照；不是板测或性能成绩。"""
import argparse
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def check(parameters, output, compiler):
    parameters = Path(parameters).resolve()
    output = Path(output).resolve()
    output.relative_to(ROOT / 'tmp')
    output.mkdir(parents=True, exist_ok=False)
    funcs = []
    sources = [ROOT / f'src/hls/{name}/cnn_hls.cpp' for name in ('ecg_cnn', 'ecg_cnn_fast')]
    environment = dict(os.environ, TMP=str(output), TEMP=str(output))
    for index, source in enumerate(sources):
        dll = output / f'network_{index}.dll'
        command = [compiler, '-shared', '-O2', '-ffp-contract=off', '-fno-fast-math',
                   '-Wno-unknown-pragmas', '-I', str(parameters), str(source), '-o', str(dll)]
        result = subprocess.run(command, capture_output=True, env=environment, timeout=120)
        (output / f'compile_{index}.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'编译失败，查看{output}')
        library = ct.CDLL(str(dll))
        func = library.cnn_hls
        func.argtypes = [ct.POINTER(ct.c_float), ct.POINTER(ct.c_float)]
        func.restype = None
        funcs.append(func)
    rng = np.random.default_rng(20261103)
    random = rng.normal(0, 1, (100, 261)).astype('f4')
    random[:, 128:131] = rng.uniform(0.25, 2, (100, 3))
    golden = np.fromfile(parameters / 'arm/input.bin', '<f4').reshape(-1, 261)
    vectors = np.concatenate((golden, random, np.zeros((1, 261), 'f4')))
    max_error = 0.0
    for vector in vectors:
        ys = []
        for func in funcs:
            result = np.empty(4, 'f4')
            func(vector.ctypes.data_as(ct.POINTER(ct.c_float)), result.ctypes.data_as(ct.POINTER(ct.c_float)))
            assert np.isfinite(result).all()
            ys.append(result)
        # 各输出的加法顺序没有变化，本机原生实现要求逐位一致。
        np.testing.assert_array_equal(ys[0].view('u4'), ys[1].view('u4'))
        max_error = max(max_error, float(np.max(np.abs(ys[0] - ys[1]))))
    summary = dict(passed=True, vectors=len(vectors), max_error=max_error,
                   seed=20261103, scope='native arithmetic equivalence only; no timing or board claim',
                   sources={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parameters', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--cxx', required=True)
    args = parser.parse_args()
    check(args.parameters, args.output, args.cxx)
