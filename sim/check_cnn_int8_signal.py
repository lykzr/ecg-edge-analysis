"""同一切拍/因果历史的FP32与W8A8离线比较；不是患者准确率验收。"""
import argparse,ctypes as ct,hashlib,json,sys
from pathlib import Path
import numpy as np
import torch
from scipy.signal import lfilter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.cnn_fourclass.network import load_model,hand_features,rr_sequence,tensor
from model.cnn_fourclass.int8_reference import Int8Reference
from ecg_model.pipeline import _features

def check(output,library,real_csv=None):
    out=Path(output).resolve();out.relative_to(ROOT/'tmp');out.mkdir(parents=True,exist_ok=False)
    lib=ct.CDLL(str(Path(library).resolve()));ptr=ct.POINTER(ct.c_float);lib.q_forward.argtypes=[ptr,ptr]
    net=load_model(0);torch.set_num_threads(1);ref=Int8Reference({k:v.numpy() for k,v in net.state_dict().items()})
    sources=[('synthetic',ROOT/'model/inference/examples/synthetic500.csv',False)]
    if real_csv:sources.append(('ads1292r',Path(real_csv),True))
    rows=[]
    for name,path,vendor in sources:
        if vendor:
            raw=np.genfromtxt(path,delimiter=',',names=True,encoding='utf-8-sig');mv=(raw['ecg_raw']-8388608)*2420/(6*8388608)
        else:mv=np.loadtxt(path,delimiter=',')
        a=500/(500+2*np.pi*.5);filtered=lfilter([a,-a],[1,-a],mv,zi=[-a*mv[0]])[0]
        z=np.copysign(np.floor(np.abs(filtered*4096)+.5),filtered)
        f=_features(np.clip(z,-32768,32767).astype('<i2'));valid=f['valid'];history=rr_sequence(f['positions500'],valid)
        x,rr,bg,count=f['x'][valid],f['rr'][valid],f['background'][valid],f['history_count'][valid]
        h=hand_features(x,rr,bg,count);hist=history[valid]
        packed=np.concatenate([x,rr,h,hist],1).astype('f4');actual=np.empty((len(x),4),'f4')
        expected=np.array([ref.forward(v) for v in packed],dtype='f4').reshape(-1,4)
        for v,y in zip(packed,actual):lib.q_forward(v.ctypes.data_as(ptr),y.ctypes.data_as(ptr))
        np.testing.assert_array_equal(actual,expected)
        with torch.no_grad():fp=np.array(net(tensor(x),tensor(rr),tensor(h),tensor(hist)).tolist(),dtype='f4').reshape(-1,4)
        confusion=np.zeros((4,4),int)
        for before,after in zip(fp.argmax(1),actual.argmax(1)):confusion[before,after]+=1
        np.savez(out/(name+'.npz'),packed=packed,fp32=fp,int8=actual,positions=f['positions500'][valid])
        rows.append(dict(source=name,input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),samples=len(mv),events=len(valid),valid=int(valid.sum()),
            class_changes=int(np.count_nonzero(fp.argmax(1)!=actual.argmax(1))),prediction_transition_matrix=confusion.tolist(),
            max_logit_error=float(np.max(np.abs(fp-actual))) if len(x) else None,c_python_exact=True))
    result=dict(passed=True,hardware=False,training=False,calibration=False,accuracy_measured=False,classes=['N','S','V','F'],
        note='矩阵行FP32预测、列INT8预测；无专家标签，不能当混淆矩阵准确率。',cases=rows)
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--library',required=True);p.add_argument('--real-csv');a=p.parse_args();check(a.output,a.library,a.real_csv)
