"""只读核研究交接包的文件和合成数值；不训练、不读取心电数据。"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np

def probability(x,model):
    raw=np.repeat(model['baseline'],len(x),axis=0);ids=np.arange(len(x))
    for stage in range(64):
        for label in range(3):
            nodes=model[f'tree_{stage}_{label}'];assert not nodes['is_categorical'].any();at=np.zeros(len(x),np.int64)
            for _ in range(int(model['max_depth'])+1):
                active=nodes['is_leaf'][at]==0
                if not active.any():break
                old=at[active];at[active]=np.where(x[ids[active],nodes['feature_idx'][old]]<=nodes['num_threshold'][old],nodes['left'][old],nodes['right'][old])
            assert nodes['is_leaf'][at].all();raw[:,label]+=nodes['value'][at]
    raw-=raw.max(1,keepdims=True);np.exp(raw,out=raw);return raw/raw.sum(1,keepdims=True)

def verify(bundle):
    manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'));assert manifest['purpose']=='RESEARCH_REVIEW_ONLY' and manifest['qualified'] is False
    for name,h in manifest['files'].items():
        path=(bundle/name).resolve();assert path.is_relative_to(bundle.resolve())
        content=path.read_bytes()
        if name in manifest.get('lf_normalized_text_files',[]):content=content.replace(b'\r\n',b'\n')
        assert hashlib.sha256(content).hexdigest()==h,name
    with np.load(bundle/'synthetic_vectors.npz',allow_pickle=False) as data:
        x=data['features'];assert x.shape==(160,192) and np.isfinite(x).all();calls=0
        for spec in manifest['models']:
            with np.load(bundle/spec['path'],allow_pickle=False) as model:
                prob=probability(x,model);np.testing.assert_allclose(prob,data[f"probability_fold_{spec['fold']}"],atol=1e-12,rtol=1e-12);np.testing.assert_array_equal(model['classes'][prob.argmax(1)],data[f"prediction_fold_{spec['fold']}"]);calls+=1
    return dict(passed=True,models=calls,synthetic_rows=len(x),features=192,fits=0,clinical_quality_test=False,qualified=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parents[1]/'data/model_review');a=p.parse_args();print(json.dumps(verify(a.bundle),ensure_ascii=False))
