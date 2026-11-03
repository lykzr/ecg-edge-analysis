"""动态INT8 Python/原生C++逐项核对，并单独报告与FP32的偏差。"""
import argparse,ctypes as ct,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.cnn_fourclass.network import load_model,hand_features,tensor,torch
from model.cnn_fourclass.int8_reference import Int8Reference


def check(output,parameters,cc):
    out=Path(output).resolve();out.relative_to(ROOT/'tmp');out.mkdir(parents=True,exist_ok=False)
    params=Path(parameters).resolve();net=load_model(0);torch.set_num_threads(4)
    reference=Int8Reference({k:v.numpy() for k,v in net.state_dict().items()})
    bridge=out/'bridge.cpp';bridge.write_text('#include "int8_core.h"\nextern "C" void q_forward(float *x,float *y){cnn_int8_core(x,y);}\n')
    dll=out/'int8.dll';cmd=[cc,'-shared','-O2','-ffp-contract=off','-Wno-unknown-pragmas','-I'+str(params),'-I'+str(ROOT/'src/hls/ecg_cnn_int8'),str(bridge),'-o',str(dll)]
    q=subprocess.run(cmd,capture_output=True,timeout=120);(out/'compile.log').write_bytes(q.stdout+q.stderr)
    if q.returncode:raise RuntimeError('INT8原生编译失败，见compile.log')
    lib=ct.CDLL(str(dll));pointer=ct.POINTER(ct.c_float);lib.q_forward.argtypes=[pointer,pointer]
    rng=np.random.default_rng(2026110301);reports=[]
    z=np.load(ROOT/'model/cnn_fourclass/assets/golden_0.npz',allow_pickle=False)
    cases=[('golden',dict(z))]
    for name,n in [('random',200),('zero',1),('constant',1)]:
        x=rng.normal(size=(n,128)).astype('f4')
        if name=='zero':x[:]=0
        if name=='constant':x[:]=1
        cases.append((name,dict(x=x,rr=rng.uniform(0,1,(n,3)).astype('f4'),background=rng.normal(size=x.shape).astype('f4'),history_count=rng.integers(0,9,n),history_rr=rng.uniform(0,1,(n,8)).astype('f4'))))
    for name,z in cases:
        hand=hand_features(z['x'],z['rr'],z['background'],z['history_count'])
        packed=np.concatenate([z['x'],z['rr'],hand,z['history_rr']],1).astype('f4');expected=np.array([reference.forward(v) for v in packed]);actual=np.empty_like(expected)
        for x,y in zip(packed,actual):lib.q_forward(x.ctypes.data_as(pointer),y.ctypes.data_as(pointer))
        np.testing.assert_array_equal(actual,expected)
        with torch.no_grad():fp=np.array(net(tensor(z['x']),tensor(z['rr']),tensor(hand),tensor(z['history_rr'])).tolist(),np.float32)
        reports.append(dict(name=name,beats=len(packed),integer_c_matches_python_exact=True,fp32_class_agreement=float(np.mean(fp.argmax(1)==actual.argmax(1))),max_logit_error=float(np.max(np.abs(fp-actual)))))
    result=dict(passed=True,hardware=False,training=False,patient_data_loaded=False,quality_qualified=False,cases=reports,
        precision='W8A8 INT32 MAC; FP32 residual/scaling/bias',commands=[cmd],weights_sha256=hashlib.sha256((params/'cnn_int8_weights.h').read_bytes()).hexdigest())
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('output','parameters','cc'):p.add_argument('--'+key,required=True)
    a=p.parse_args();check(a.output,a.parameters,a.cc)
