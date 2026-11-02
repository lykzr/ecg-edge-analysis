"""只导出H27 fold0 FP32权重和黄金输入，不量化、不训练。"""
from pathlib import Path
import sys,json,hashlib,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from model.cnn_fourclass.network import load_model,hand_features,tensor,torch

def export(output):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    source=ROOT/'model/cnn_fourclass/assets/fold_0.pt'
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    assert sha=='16d56a6b1065df35f3e11c4cc285055b421978bd451d5da1b72df8f1744fcfc7'
    net=load_model(0);state=net.state_dict();flat=[];offsets={};defines=[]
    for name,value in state.items():
        offsets[name]=dict(offset=len(flat),shape=list(value.shape));defines.append('#define W_'+name.upper().replace('.','_')+' '+str(len(flat)))
        flat.extend(value.flatten().tolist())
    assert len(flat)==25482 # 参数25476及RR归一化6个buffer
    (output/'cnn_offsets.h').write_text('\n'.join(defines)+'\n')
    (output/'cnn_weights.c').write_text('#include "cnn.h"\nconst float cnn_weights[]={\n'+',\n'.join(float(v).hex()+'f' for v in flat)+'\n};\n')
    z=np.load(ROOT/'model/cnn_fourclass/assets/golden_0.npz');hand=hand_features(z['x'],z['rr'],z['background'],z['history_count'])
    x=np.concatenate([z['x'],z['rr'],hand,z['history_rr']],1).astype('<f4')
    x.tofile(output/'input.bin');z['logits'].astype('<f4').tofile(output/'expected.bin')
    info=dict(model_sha256=sha,fold=0,precision='FP32',weights=len(flat),offsets=offsets,vectors=len(x),torch_version=torch.__version__,fits=0)
    (output/'export.json').write_text(json.dumps(info,indent=2)+'\n');return info

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);print(json.dumps(export(p.parse_args().output)))
