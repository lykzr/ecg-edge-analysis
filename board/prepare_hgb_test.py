"""生成ARM整段验收的固定合成/边界输入与原模型参考；无患者、无训练。"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'sim'),str(ROOT/'model/inference')]
from check_hgb_arm import reference
from ecg_model.pipeline import infer_mv, DT
from ecg_model.tree_model import probability

def prepare(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    signal=np.loadtxt(ROOT/'model/inference/examples/synthetic500.csv',delimiter=',')
    cases=[]
    for mode in ('hp05','raw'):
        full=infer_mv(signal,fold=0,preprocess=mode)
        cases.append((f'synthetic_{mode}',full['requests'],len(signal),full))
    rng=np.random.default_rng(20261101)
    for mode in ('random','zero','constant','alternating'):
        n=480;r=np.zeros(n,DT)
        r['generation']=3;r['beat_id']=np.arange(1,n+1);r['sampling_hz']=500
        pos=np.cumsum(rng.integers(90,1700,size=n)).astype(np.int64)
        r['position']=(pos-pos[0]+100).astype(np.uint32)
        r['ready_at']=np.maximum.accumulate(r['position']+rng.integers(266,750,n).astype(np.uint32))
        r['rr_samples'][1:]=np.diff(r['position']);r['input_status'][0]=4
        r['waveform']=rng.normal(size=(n,128)).astype(np.float32)
        r['rr']=rng.uniform(0,1,(n,3)).astype(np.float32)
        if mode=='zero':r['waveform']=0
        if mode=='constant':r['waveform']=-2
        if mode=='alternating':r['waveform']=np.tile([1,-1],64)
        cases.append((mode,r,int(r['ready_at'][-1])+1,None))
    r=np.zeros(4,DT);r['generation']=1;r['beat_id']=[1,2,3,4];r['sampling_hz']=500
    r['position']=[200,600,1000,1400];r['ready_at']=[466,866,1266,1500]
    r['rr_samples']=[0,400,400,400];r['input_status']=[2,0,0,4]
    r['waveform'][:,44]=-1;r['waveform'][:,59]=1
    cases.append(('boundary',r,1501,None))
    with np.load(ROOT/'model/inference/assets/v92_fold0.npz',allow_pickle=False) as model:
        code=['#include "hgb_fixture.h"','const double hgb_signal[30000]={']
        code.extend(','.join(float(v).hex() for v in signal[i:i+8])+',' for i in range(0,len(signal),8));code.append('};')
        counts=[];samples=[];names=[]
        for i,(name,r,n,full) in enumerate(cases):
            f,decision,history=reference(r,n)
            valid=r['input_status']==0;p=np.full((len(r),3),np.nan)
            p[valid]=probability(f[valid],model)
            cls=np.full(len(r),-1,np.int32);cls[valid]=p[valid].argmax(1)
            np.savez(output/f'{name}.npz',requests=r,features=f,probabilities=p,decision_at=decision,history=history,class_id=cls)
            if i>=2:
                code.append(f'const HgbRequest hgb_fixture_{i}[{len(r)}]={{')
                for row in r:
                    fields=','.join(str(int(row[k])) for k in DT.names[:7])
                    wave=','.join(float(v).hex()+'f' for v in row['waveform'])
                    rr=','.join(float(v).hex()+'f' for v in row['rr'])
                    code.append('{'+fields+',{'+wave+'},{'+rr+'}},')
                code.append('};')
            counts.append(len(r));samples.append(n);names.append(name)
        code.append('const HgbRequest *const hgb_fixtures[7]={0,0,'+','.join('hgb_fixture_'+str(i) for i in range(2,7))+'};')
        code.append('const uint32_t hgb_counts[7]={'+','.join(map(str,counts))+'};')
        code.append('const uint32_t hgb_samples[7]={'+','.join(map(str,samples))+'};')
    (output/'hgb_fixture.c').write_text('\n'.join(code)+'\n',encoding='ascii')
    (output/'hgb_fixture.h').write_text('#include "hgb.h"\nextern const double hgb_signal[30000];\nextern const HgbRequest *const hgb_fixtures[7];\nextern const uint32_t hgb_counts[7],hgb_samples[7];\n#define HGB_TEST_RESULTS '+str(sum(counts))+'\n',encoding='ascii')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    receipt=dict(cases=names,counts=counts,samples=samples,files=files,seed=20261101,fits=0,scope='synthetic/context fixtures; not patient accuracy')
    (output/'fixture.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    prepare(p.parse_args().output)
