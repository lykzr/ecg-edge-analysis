"""导出独立动态INT8候选，不修改FP32权重、不读患者、不训练。"""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.cnn_fourclass.network import load_model,hand_features
from model.cnn_fourclass.int8_reference import Int8Reference


def export(output):
    out=Path(output).resolve();out.relative_to(ROOT/'tmp');out.mkdir(parents=True,exist_ok=False)
    state={k:v.detach().numpy() for k,v in load_model(0).state_dict().items()};ref=Int8Reference(state)
    convnames=['wave.0.weight']+[f'wave.{b}.body.{c}.weight' for b in (3,4,5) for c in (0,3)]
    dense=['rr.0','head.0','head.3'];banks=[[] for _ in range(8)];scales=[]
    for name in convnames:
        w,s=ref.weights[name]
        for lane in range(8):banks[lane].extend(w[lane::8].reshape(-1).tolist())
        scales.extend(s.reshape(-1).tolist())
    weights=[];ds=[];bias=[]
    for name in dense:
        w,s=ref.weights[name+'.weight'];weights.extend(w.reshape(-1).tolist());ds.extend(s.reshape(-1).tolist());bias.extend(state[name+'.bias'].tolist())
    def nums(v):return ','.join(str(int(x)) for x in v)
    def floats(v):return ','.join(format(float(x),'.9e')+'f' for x in v)
    text='#include <stdint.h>\nstatic const int8_t q_conv_weights[8][988]={'+','.join('{'+nums(v)+'}' for v in banks)+'};\n'
    for name,typ,data in [('q_conv_scales','float',scales),('q_dense_weights','int8_t',weights),('q_dense_scales','float',ds),('q_dense_bias','float',bias),('q_rr_mean','float',state['rr_mean']),('q_rr_std','float',state['rr_std'])]:
        text+=f'static const {typ} {name}[{len(data)}]={{'+(nums(data) if typ=='int8_t' else floats(data))+'};\n'
    (out/'cnn_int8_weights.h').write_text(text,encoding='utf-8')
    z=np.load(ROOT/'model/cnn_fourclass/assets/golden_0.npz',allow_pickle=False)
    packed=np.concatenate([z['x'],z['rr'],hand_features(z['x'],z['rr'],z['background'],z['history_count']),z['history_rr']],1).astype('<f4')
    actual=np.array([ref.forward(v) for v in packed]);packed.tofile(out/'input.bin');actual.tofile(out/'expected.bin')
    (out/'cnn_int8_vectors.h').write_text('static const float q_inputs[12][261]={'+','.join('{'+floats(v)+'}' for v in packed)+'};\nstatic const float q_expected[12][4]={'+','.join('{'+floats(v)+'}' for v in actual)+'};\n')
    info=dict(version='H27-DYNAMIC-W8A8-v1',fold=0,source_sha256=hashlib.sha256((ROOT/'model/cnn_fourclass/assets/fold_0.pt').read_bytes()).hexdigest(),
        precision='W8A8-INT32-MAC-FP32-glue',calibration='none: per-input dynamic power-of-two scales',weight_scale='per output channel',
        rounding='nearest ties away from zero',range=[-127,127],accumulator='int32',
        max_accumulator_bound=269*127*127,weight_bytes=len(weights)+sum(map(len,banks)),training=False,test_loaded=False,
        golden_class_agreement=float(np.mean(actual.argmax(1)==z['logits'].argmax(1))),golden_max_logit_error=float(np.max(np.abs(actual-z['logits']))),
        header_sha256=hashlib.sha256((out/'cnn_int8_weights.h').read_bytes()).hexdigest(),qualified=False)
    (out/'export.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info));return info

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);export(p.parse_args().output)
