"""导出H27 FP32四路卷积ROM及HLS黄金向量，不训练、不量化。"""
import argparse,json,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'build')]
from export_cnn_arm import export
from model.cnn_fourclass.network import load_model
def run(output):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    info=export(output/'arm');s=load_model(0).state_dict();banks=[[] for _ in range(4)]
    convnames=['wave.0.weight']+[f'wave.{b}.body.{c}.weight' for b in (3,4,5) for c in (0,3)]
    for name in convnames:
        w=s[name].numpy()
        for lane in range(4):banks[lane].extend(w[lane::4].reshape(-1).tolist())
    dense=[]
    for name in ('rr.0.weight','rr.0.bias','head.0.weight','head.0.bias','head.3.weight','head.3.bias'):dense.extend(s[name].flatten().tolist())
    assert len(dense)==17572 and all(len(v)==1976 for v in banks)
    def values(a):return ','.join(format(float(v),'.9e')+'f' for v in a)
    header='// 冻结H27 fold0，float32九位十进制往返精确。\nstatic const float conv_weights[4][1976]={\n'+',\n'.join('{'+values(v)+'}' for v in banks)+'\n};\n'
    header+='static const float dense_weights[17572]={'+values(dense)+'};\n'
    for name in ('rr_mean','rr_std'):header+=f'static const float {name}[3]={{'+values(s[name].tolist())+'};\n'
    (output/'cnn_hls_weights.h').write_text(header,encoding='utf-8')
    x=np.fromfile(output/'arm/input.bin','<f4').reshape(-1,261);y=np.fromfile(output/'arm/expected.bin','<f4').reshape(-1,4)
    (output/'cnn_hls_vectors.h').write_text('static const float inputs[12][261]={'+','.join('{'+values(v)+'}' for v in x)+'};\nstatic const float expected[12][4]={'+','.join('{'+values(v)+'}' for v in y)+'};\n',encoding='utf-8')
    (output/'export.json').write_text(json.dumps(dict(model=info,rom_sha256=hashlib.sha256((output/'cnn_hls_weights.h').read_bytes()).hexdigest()),indent=2)+'\n')
    print(output)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);run(p.parse_args().output)
