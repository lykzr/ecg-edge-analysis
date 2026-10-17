"""公开MF-CNN思路的独立NumPy改编：固定模板卷积，训练共享RR分支与分类头。

来源/区别见docs/cnn_baseline.md；不是作者代码、预训练权重或INT8实现。
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def morphology(x, kernels, batch=1024):
    """Keras SAME的偶数核约定：左15/右16，逐位置相关后全局最大池化。"""
    out=[]
    for start in range(0,len(x),batch):
        windows=sliding_window_view(np.pad(x[start:start+batch],((0,0),(15,16))),32,axis=1)
        response=windows@kernels.T
        out.append(response.max(axis=1))
    return np.concatenate(out).astype(np.float32)


def initialize(seed, morphology_channels=4, rr_features=3, classes=4):
    rng=np.random.default_rng(seed)
    params={}
    for name,inputs,outputs in [('r1',1,32),('r2',32,16),('r3',16,8),('head',morphology_channels+rr_features*8,classes)]:
        params[name+'w']=(rng.standard_normal((inputs,outputs))*np.sqrt(2/inputs)).astype(np.float32)
        params[name+'b']=np.zeros(outputs,dtype=np.float32)
    return params


def forward(params, morph, rr, cache=False):
    x=rr[:,:,None]; history=[]
    for name in ('r1','r2','r3'):
        z=x@params[name+'w']+params[name+'b']
        history.append((name,x,z))
        x=np.maximum(z,0)
    fused=np.concatenate([morph,x.reshape(len(x),-1)],axis=1)
    logits=fused@params['headw']+params['headb']
    return (logits,(history,fused,morph.shape[1])) if cache else logits


def loss_grad(params,morph,rr,labels,class_weights):
    logits,(history,fused,nm)=forward(params,morph,rr,True)
    shifted=logits-logits.max(axis=1,keepdims=True)
    exp=np.exp(shifted);prob=exp/exp.sum(axis=1,keepdims=True)
    weights=class_weights[labels];den=weights.sum()
    # log-sum-exp保持大logit时的数值稳定，不对概率裁剪来改变梯度。
    loss=np.sum(weights*(np.log(exp.sum(axis=1))-shifted[np.arange(len(labels)),labels]))/den
    d=prob.copy();d[np.arange(len(labels)),labels]-=1;d*=weights[:,None]/den
    grad={'headw':fused.T@d,'headb':d.sum(axis=0)}
    dx=(d@params['headw'].T)[:,nm:].reshape(len(labels),rr.shape[1],8)
    for name,x,z in reversed(history):
        dz=dx*(z>0)
        grad[name+'w']=x.reshape(-1,x.shape[-1]).T@dz.reshape(-1,dz.shape[-1])
        grad[name+'b']=dz.sum(axis=(0,1))
        dx=dz@params[name+'w'].T
    return float(loss),grad


def scores(labels,prediction,classes=4):
    matrix=np.bincount(classes*labels+prediction,minlength=classes*classes).reshape(classes,classes)
    tp=matrix.diagonal().astype(float)
    precision=np.divide(tp,matrix.sum(axis=0),out=np.zeros(classes),where=matrix.sum(axis=0)>0)
    recall=np.divide(tp,matrix.sum(axis=1),out=np.zeros(classes),where=matrix.sum(axis=1)>0)
    f1=np.divide(2*precision*recall,precision+recall,out=np.zeros(classes),where=precision+recall>0)
    return {'confusion_matrix_rows_true':matrix.tolist(),'support':matrix.sum(axis=1).tolist(),
            'precision':precision.tolist(),'recall':recall.tolist(),'f1':f1.tolist(),
            'macro_f1':float(f1.mean()),'accuracy':float(tp.sum()/matrix.sum())}
