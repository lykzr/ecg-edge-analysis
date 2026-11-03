"""独立复算CNN串口结果，核对位置、状态、类别与概率；不操作板卡。"""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.special import softmax
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.cnn_fourclass.network import classify_mv
def verify(directory,input_mv):
    directory=Path(directory);path=Path(input_mv);r=json.loads((directory/'result.json').read_text(encoding='utf-8'))
    assert r['passed'] and r['classifier']=='CNN-H27-fold0' and r['execution_location'] in ('zynq_arm','zynq_pl') and r['precision'] in ('FP32','W8A8')
    expected=classify_mv(np.loadtxt(path,delimiter=','),fold=0,preprocess=r['preprocess']);rows=r['events'];valid=expected['valid']
    if r['precision']=='W8A8':
        from scipy.signal import lfilter
        from model.cnn_fourclass.network import load_model,hand_features,rr_sequence
        from model.cnn_fourclass.int8_reference import Int8Reference
        from ecg_model.pipeline import _features
        x=np.loadtxt(path,delimiter=',')
        if r['preprocess']=='hp05':
            a=500/(500+2*np.pi*.5);x=lfilter([a,-a],[1,-a],x,zi=[-a*x[0]])[0]
        z=np.copysign(np.floor(np.abs(x*4096)+.5),x);f=_features(np.clip(z,-32768,32767).astype('<i2'))
        hist=rr_sequence(f['positions500'],f['valid']);hand=hand_features(f['x'][valid],f['rr'][valid],f['background'][valid],f['history_count'][valid])
        packed=np.concatenate([f['x'][valid],f['rr'][valid],hand,hist[valid]],1).astype('f4')
        net=load_model(0);q=Int8Reference({k:v.numpy() for k,v in net.state_dict().items()})
        expected['logits'][valid]=np.array([q.forward(v) for v in packed],dtype='f4').reshape(-1,4)
        expected['prediction'][valid]=expected['logits'][valid].argmax(1)
    np.testing.assert_array_equal([v['position'] for v in rows],expected['positions500'])
    np.testing.assert_array_equal([v['ready_at'] for v in rows],expected['ready500'])
    np.testing.assert_array_equal([v['status']==0 for v in rows],valid)
    np.testing.assert_array_equal([v['class_id'] for v in rows],expected['prediction'])
    got=np.array([v['probability'] for v in rows],dtype=float)[valid];p=softmax(expected['logits'][valid],axis=1)
    np.testing.assert_allclose(got,p,atol=2e-5,rtol=2e-4)
    assert r['clipped']==expected['clipped_samples']
    result=dict(passed=True,precision=r['precision'],source='actual board UART versus frozen PyTorch' if r['precision']=='FP32' else 'actual board UART versus Python W8A8 integer reference',samples=r['samples'],events=len(rows),valid=int(valid.sum()),classes_exact=True,max_probability_error=float(np.max(np.abs(got-p))) if len(p) else 0,compute_us=r['compute_us'],classify_mean_us=r['compute_us']['classify']/int(valid.sum()) if valid.any() else None,counts={name:sum(v['label']==name for v in rows) for name in ('N','S','V','F','UNCLASSIFIED')},input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),result_sha256=hashlib.sha256((directory/'result.json').read_bytes()).hexdigest(),tx_sha256=hashlib.sha256((directory/'tx.bin').read_bytes()).hexdigest(),rx_sha256=hashlib.sha256((directory/'rx.log').read_bytes()).hexdigest(),flash_written=False,accuracy_measured=False)
    (directory/'comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--input-mv',required=True);a=p.parse_args();verify(a.directory,a.input_mv)
