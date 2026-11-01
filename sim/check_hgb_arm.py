"""编译实际可移植C，逐维核对冻结Python特征/分类；无训练、患者或板卡操作。"""
from pathlib import Path
import argparse
import ctypes as ct
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'model/inference'), str(ROOT / 'build')]
from ecg_model.pipeline import infer_mv, DT, CONFIG
from ecg_model.tree_model import probability
from ecg_model.ecg_relative_features import aligned, relative_features
from ecg_model.ecg_band_features import band_features
from ecg_model.ecg_next_rr import next_rr
from ecg_model.ecg_rr_dispersion import rr_dispersion
from ecg_model.ecg_hermite_shape import hermite_features
from export_hgb import export


class Request(ct.Structure):
    _fields_ = [(n, ct.c_uint32) for n in ('generation', 'beat_id', 'position', 'rr_samples', 'sampling_hz', 'ready_at', 'input_status')] + [('waveform', ct.c_float * 128), ('rr', ct.c_float * 3)]


class Result(ct.Structure):
    _fields_ = [(n, ct.c_uint32) for n in ('beat_id', 'position', 'decision_at', 'status', 'history_count')] + [('class_id', ct.c_int32), ('features', ct.c_float * 192), ('probability', ct.c_double * 3)]


class Input(ct.Structure):
    _fields_ = [('previous_input', ct.c_double), ('previous_output', ct.c_double), ('clipped', ct.c_uint32), ('started', ct.c_uint32), ('highpass', ct.c_uint32)]


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def reference(requests, samples):
    """仅组装冻结函数；上下文由事件/ready独立计算，不从C输出倒推。"""
    r = requests
    n = len(r)
    position, ready = r['position'].astype(np.int64), r['ready_at'].astype(np.int64)
    valid = r['input_status'] == 0
    bg = np.zeros((n, 128), np.float32)
    count = np.zeros(n, np.int32)
    for i in range(n):
        history = np.flatnonzero((np.arange(n) < i) & (r['input_status'] != 4) & (ready <= position[i]))[-8:]
        if len(history):
            bg[i] = np.median(aligned(r['waveform'][history]), axis=0).astype(np.float32)
            count[i] = len(history)
    base = np.zeros((n, 159), np.float32)
    rel, _ = relative_features(r['waveform'][valid], r['rr'][valid], bg[valid], count[valid])
    band, _ = band_features(r['waveform'][valid], bg[valid], count[valid])
    base[valid] = np.c_[rel, (np.clip(r['rr_samples'][valid].astype(float)/500, 0, 4)/4).astype(np.float32), band]
    following = next_rr(position, ready, samples, valid, 1250)
    with np.load(ROOT / 'model/inference/assets/hermite_basis.npz', allow_pickle=False) as z:
        hermite = hermite_features(r['waveform'], bg, count, valid, z['basis'])
    features = np.c_[base, following['extra'], rr_dispersion(position), hermite]
    return features, following['decision_at'], count


def verify(output, cc=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    exported = export(output / 'parameters')
    compiler = cc or os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
    if not compiler:
        raise RuntimeError('缺少已有GCC；不安装、不跳过实际C核验')
    source = ROOT / 'src/ps/ecg_hgb'
    library = output / ('hgb.dll' if os.name == 'nt' else 'hgb.so')
    command = [compiler, '-std=c11', '-O2', '-ffp-contract=off', '-fno-fast-math', '-Wall', '-Wextra', '-Werror', '-shared']
    if os.name != 'nt':
        command += ['-fPIC']
    native = ROOT / 'model/inference/native'
    # 原交付C保留原字节；其既有紧凑缩进警告单独记录，不降低新实现的-Werror。
    compile_flags = command[:-1]  # 去掉-shared，先分别编译为对象。
    objects = []
    commands = []
    env = dict(os.environ, TMP=str(output), TEMP=str(output), TMPDIR=str(output))
    started = time.monotonic()
    sources = [source / n for n in ('features.c','tree.c','prepare.c')] + [output / 'parameters/hgb_parameters.c']
    sources += [native / n for n in ('pipeline500.c','rate500.c','classification.c','runtime500_bridge.c')]
    with (output / 'compile.log').open('wb') as log:
        for i,p in enumerate(sources):
            obj=output / f'part{i}.o';objects.append(obj)
            cmd = compile_flags + ['-I'+str(source),'-I'+str(native),'-include',str(source/'frozen.h'),'-c',str(p),'-o',str(obj)]
            if p.parent == native:cmd += ['-Wno-error=misleading-indentation']
            commands.append(cmd)
            result=subprocess.run(cmd,capture_output=True,timeout=120,env=env)
            log.write(result.stdout+result.stderr)
            if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        command=[compiler,'-shared',*[str(p) for p in objects],'-lm','-o',str(library)]
        commands.append(command)
        result=subprocess.run(command,capture_output=True,timeout=120,env=env)
        log.write(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    lib = ct.CDLL(str(library))
    lib.ecg_hgb_probability.argtypes = [ct.POINTER(ct.c_float), ct.POINTER(ct.c_double)]
    lib.ecg_hgb_record.argtypes = [ct.POINTER(Request), ct.c_size_t, ct.c_uint32, ct.POINTER(Result)]
    lib.ecg_hgb_workspace_size.argtypes=[ct.c_uint32];lib.ecg_hgb_workspace_size.restype=ct.c_size_t
    lib.ecg_hgb_prepare.argtypes=[ct.POINTER(ct.c_int16),ct.c_uint32,ct.POINTER(Request),ct.c_uint32,ct.c_void_p,ct.c_size_t,ct.POINTER(ct.c_uint32)]
    lib.ecg_hgb_input.argtypes=[ct.POINTER(Input),ct.POINTER(ct.c_double),ct.c_size_t,ct.c_int,ct.POINTER(ct.c_int16)]
    assert ct.sizeof(Request) == DT.itemsize == 552
    with np.load(ROOT / 'model/inference/assets/v92_fold0.npz', allow_pickle=False) as model:
        def tree(x):
            x = np.asarray(x, dtype=np.float32)
            p = (ct.c_double * 3)()
            rc = lib.ecg_hgb_probability(x.ctypes.data_as(ct.POINTER(ct.c_float)), p)
            assert rc == 0
            return np.array(p)
        with np.load(ROOT / 'model/inference/examples/feature_vectors.npz', allow_pickle=False) as vectors:
            features = vectors['features'].astype(np.float32)
            expected = probability(features, model)
        actual = np.array([tree(x) for x in features])
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(actual.argmax(1), expected.argmax(1))
        # 每个内部节点两侧的邻近float32边界都要核树分支，不只随机特征。
        edge = []
        for key in model.files:
            if key.startswith('tree_'):
                for row in model[key]:
                    if not row['is_leaf']:
                        at = int(row['feature_idx']); threshold = np.float32(row['num_threshold'])
                        for v in (np.nextafter(threshold, np.float32(-np.inf)), threshold, np.nextafter(threshold, np.float32(np.inf))):
                            x = np.zeros(192, np.float32);x[at] = v;edge.append(x)
        edge = np.array(edge, dtype=np.float32)
        expected_edge = probability(edge, model)
        actual_edge = np.array([tree(x) for x in edge])
        np.testing.assert_allclose(actual_edge, expected_edge, rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(actual_edge.argmax(1), expected_edge.argmax(1))
        reports = []
        def compare(name, requests, samples, full=None):
            requests = np.array(requests, dtype=DT, copy=True)
            features, decision, count = reference(requests, samples)
            rows = (Request * len(requests)).from_buffer_copy(requests.tobytes())
            results = (Result * len(requests))()
            assert lib.ecg_hgb_record(rows, len(rows), samples, results) == 0, name
            got = np.array([list(v.features) for v in results], dtype=np.float32).reshape(-1, 192)
            np.savez(output / (name + '.npz'), requests=requests, expected=features, actual=got)
            # 预先固定浮点运算重排容差；类别必须逐拍完全一致。
            np.testing.assert_allclose(got, features, rtol=2e-6, atol=2e-6, err_msg=name)
            np.testing.assert_array_equal([v.decision_at for v in results], decision)
            np.testing.assert_array_equal([v.history_count for v in results], count)
            np.testing.assert_array_equal([v.status for v in results], requests['input_status'])
            valid = requests['input_status'] == 0
            expected_p = probability(features[valid], model)
            got_p = np.array([list(v.probability) for v in results])[valid]
            np.testing.assert_allclose(got_p, expected_p, rtol=1e-10, atol=1e-10, err_msg=name)
            np.testing.assert_array_equal(np.array([v.class_id for v in results])[valid], expected_p.argmax(1))
            for v in results:
                if v.status:assert v.class_id == -1 and np.isnan(list(v.probability)).all()
            if full is not None:
                np.testing.assert_array_equal(features, full['features'])
                np.testing.assert_array_equal(decision, full['decision_at'])
                np.testing.assert_allclose(got_p, full['probabilities'][valid], rtol=1e-10, atol=1e-10)
            reports.append(dict(name=name, events=len(requests), valid=int(valid.sum()),
                                feature_max_abs=float(np.max(np.abs(got-features), initial=0)),
                                probability_max_abs=float(np.max(np.abs(got_p-expected_p), initial=0)),
                                classes_equal=True, decisions_equal=True))
            return rows, results
        signal = np.loadtxt(ROOT / 'model/inference/examples/synthetic500.csv', delimiter=',')
        input_cases=[]
        for preprocess in ('hp05', 'raw'):
            full = infer_mv(signal, fold=0, preprocess=preprocess)
            codes=np.zeros(len(signal),np.int16);state=Input()
            # 137点分块，保持滤波状态，不以每块重置冒充连续输入。
            for start in range(0,len(signal),137):
                chunk=np.ascontiguousarray(signal[start:start+137],dtype=np.float64)
                assert lib.ecg_hgb_input(ct.byref(state),chunk.ctypes.data_as(ct.POINTER(ct.c_double)),len(chunk),int(preprocess=='hp05'),codes[start:].ctypes.data_as(ct.POINTER(ct.c_int16)))==0
            from scipy.signal import lfilter
            a=500/(500+2*np.pi*.5)
            y=lfilter([a,-a],[1,-a],signal,zi=[-a*signal[0]])[0] if preprocess=='hp05' else signal
            scaled=np.copysign(np.floor(np.abs(y*4096)+.5),y)
            expected_codes=np.clip(scaled,-32768,32767).astype(np.int16)
            np.testing.assert_array_equal(codes,expected_codes)
            assert state.clipped==full['clipped_samples']
            workspace=ct.create_string_buffer(lib.ecg_hgb_workspace_size(len(codes)))
            requests=(Request*200)();count=ct.c_uint32()
            assert lib.ecg_hgb_prepare(codes.ctypes.data_as(ct.POINTER(ct.c_int16)),len(codes),requests,200,workspace,len(workspace),ct.byref(count))==0
            got_requests=np.frombuffer(bytes(requests),dtype=DT,count=count.value).copy()
            np.testing.assert_array_equal(got_requests,full['requests'])
            compare('synthetic_' + preprocess, got_requests, len(signal), full)
            assert lib.ecg_hgb_prepare(codes.ctypes.data_as(ct.POINTER(ct.c_int16)),len(codes),requests,1,workspace,len(workspace),ct.byref(count))==-3
            assert count.value==0
            input_cases.append(dict(preprocess=preprocess,source_samples=len(codes),requests_equal=True,
                                    quantized_input_equal=True,workspace_bytes=len(workspace)))
        rng = np.random.default_rng(20261101)
        for mode in ('random', 'zero', 'constant', 'alternating'):
            n = 480
            r = np.zeros(n, DT)
            r['generation'] = 3;r['beat_id'] = np.arange(1, n+1);r['sampling_hz'] = 500
            r['position'] = np.cumsum(rng.integers(90, 1700, size=n)).astype(np.uint32)
            r['position'] = (r['position'].astype(np.int64)-int(r['position'][0])+100).astype(np.uint32)
            r['ready_at'] = np.maximum.accumulate(r['position'] + rng.integers(266, 750, n).astype(np.uint32))
            samples = int(r['ready_at'][-1]) + 1
            r['rr_samples'][1:] = np.diff(r['position']);r['input_status'][0] = 4
            r['waveform'] = rng.normal(size=(n, 128)).astype(np.float32)
            r['rr'] = rng.uniform(0, 1, (n, 3)).astype(np.float32)
            if mode == 'zero':r['waveform'] = 0
            if mode == 'constant':r['waveform'] = -2
            if mode == 'alternating':r['waveform'] = np.tile([1, -1], 64)
            compare(mode, r, samples)
        # 末端不足、首RR未知、相同abs峰的最早选择及末端等待均覆盖。
        r = np.zeros(4, DT);r['generation']=1;r['beat_id']=[1,2,3,4];r['sampling_hz']=500
        r['position']=[200,600,1000,1400];r['ready_at']=[466,866,1266,1500]
        r['rr_samples']=[0,400,400,400];r['input_status']=[2,0,0,4]
        r['waveform'][:,44]=-1;r['waveform'][:,59]=1
        rows, results = compare('boundary',r,1501)
        # 明确拒绝非法输入，不向正常拍退化；不越界或读未来。
        rejected=0
        for field,value in [('generation',0),('beat_id',99),('sampling_hz',360),('rr_samples',999),('input_status',7),('ready_at',1501),('position',0)]:
            bad=r.copy();bad[field][1]=value
            assert lib.ecg_hgb_record((Request*4).from_buffer_copy(bad.tobytes()),4,1501,results)==-1
            rejected+=1
        bad=r.copy();bad['waveform'][1,0]=np.nan
        assert lib.ecg_hgb_record((Request*4).from_buffer_copy(bad.tobytes()),4,1501,results)==-1;rejected+=1
        assert lib.ecg_hgb_record(None,0,1501,None)==0
        assert lib.ecg_hgb_record(None,30001,1501,None)==-1
        bad=np.zeros(192,np.float32);bad[0]=np.inf
        assert lib.ecg_hgb_probability(bad.ctypes.data_as(ct.POINTER(ct.c_float)),(ct.c_double*3)())==-1
        conversion_rejected=0
        state=Input();block=np.array([.25,-.25,0,16,-16],np.float64);codes=np.zeros(len(block),np.int16)
        assert lib.ecg_hgb_input(ct.byref(state),block.ctypes.data_as(ct.POINTER(ct.c_double)),len(block),0,codes.ctypes.data_as(ct.POINTER(ct.c_int16)))==0
        np.testing.assert_array_equal(codes,[1024,-1024,0,32767,-32768]);assert state.clipped==2
        assert lib.ecg_hgb_input(ct.byref(state),None,0,1,None)==-1;conversion_rejected+=1
        snapshot=bytes(state);block[0]=np.nan
        assert lib.ecg_hgb_input(ct.byref(state),block.ctypes.data_as(ct.POINTER(ct.c_double)),len(block),0,codes.ctypes.data_as(ct.POINTER(ct.c_int16)))==-1
        assert bytes(state)==snapshot;conversion_rejected+=1
        # 半值远离零、正负对称与饱和，不用Python默认的银行家舍入。
        block=np.array([.5,1.5,2.5,-.5,-1.5,-2.5],np.float64)/4096
        codes=np.zeros(len(block),np.int16);state=Input()
        assert lib.ecg_hgb_input(ct.byref(state),block.ctypes.data_as(ct.POINTER(ct.c_double)),len(block),0,codes.ctypes.data_as(ct.POINTER(ct.c_int16)))==0
        np.testing.assert_array_equal(codes,[1,2,3,-1,-2,-3])
        # 无事件及单点，非法对齐/工作区不足、错误输入长度。
        small=np.zeros(30,np.int16);workspace=ct.create_string_buffer(lib.ecg_hgb_workspace_size(30));requests=(Request*1)();count=ct.c_uint32()
        assert lib.ecg_hgb_prepare(small.ctypes.data_as(ct.POINTER(ct.c_int16)),30,requests,1,workspace,len(workspace),ct.byref(count))==0 and count.value==0
        assert lib.ecg_hgb_prepare(small.ctypes.data_as(ct.POINTER(ct.c_int16)),30,requests,1,workspace,len(workspace)-1,ct.byref(count))==-1
        assert lib.ecg_hgb_prepare(small.ctypes.data_as(ct.POINTER(ct.c_int16)),30,requests,1,ct.addressof(workspace)+1,len(workspace),ct.byref(count))==-1
        assert lib.ecg_hgb_workspace_size(0)==lib.ecg_hgb_workspace_size(1800001)==0
    summary=dict(passed=True, fits=0, hardware_operated=False, arm_executed=False,seed=20261101,
                 environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
                 scope='host-compiled complete C record pipeline, features/tree; not continuous board deployment',
                 model=exported, tree_vectors=len(features), threshold_vectors=len(edge),
                 cases=reports,input_cases=input_cases, rejected=rejected, conversion_rejected=conversion_rejected, feature_rtol=2e-6,feature_atol=2e-6,
                 probability_rtol=1e-10,probability_atol=1e-10,
                 seconds=time.monotonic()-started,compiler=compiler,commands=commands,
                 sources={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in [source/'hgb.h',source/'frozen.h',source/'features.c',source/'tree.c',source/'prepare.c',Path(__file__),ROOT/'build/export_hgb.py']},
                 reference_sources={p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/'model/inference').rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    (output/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--cc')
    args=parser.parse_args()
    result=verify(args.output,args.cc)
    print(json.dumps({k:result[k] for k in ('passed','fits','arm_executed','tree_vectors','threshold_vectors','cases','input_cases','rejected')},ensure_ascii=False))
