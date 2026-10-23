"""v3：训练集RR标准化、自然分布加权损失及可选增强，无测试选型。"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time
import numpy as np
import torch
from torch import nn

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_trainable_cnn import create_model,budget
from ecg_mf_cnn import scores
from train_cnn_candidates import load_split,save_json,digest,evaluate,gate


def remove_bn(module):
    for name,child in list(module.named_children()):
        if isinstance(child,nn.BatchNorm1d):
            setattr(module,name,nn.Identity())
        else:
            remove_bn(child)


def construct(config):
    model=create_model(config)
    if config['batch_norm']=='none':
        remove_bn(model)
    return model


def augment(x):
    # 仅训练：中心±8%时间伸缩、±2点偏移、幅值0.8—1.2、少量白噪声。
    n,length=x.shape;center=length/2
    positions=(torch.arange(length)[None,:]-center)*torch.empty(n,1).uniform_(.92,1.08)+center+torch.randint(-2,3,(n,1))
    lo=positions.floor().long();hi=lo+1;a=positions-lo
    b=torch.arange(n)[:,None]
    v0=x[b,lo.clamp(0,length-1)]*((lo>=0)&(lo<length))
    v1=x[b,hi.clamp(0,length-1)]*((hi>=0)&(hi<length))
    return (v0*(1-a)+v1*a)*torch.empty(n,1).uniform_(.8,1.2)+torch.randn_like(x)*.015


def fit(config,cfg,train,val,normalization,out,limits):
    seed=cfg['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    model=construct(config);resources=budget(model)
    opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
    x,rr,y=train;counts=torch.bincount(y,minlength=4)
    weights=(len(y)/(4*counts.float()))**config['weight_power'];weights/=weights.mean()
    generator=torch.Generator().manual_seed(seed)
    best=-1.;best_loss=float('inf');best_epoch=0;best_metrics=None
    for epoch in range(1,cfg['max_epochs']+1):
        model.train();start=time.perf_counter();total=0.
        order=torch.randperm(len(y),generator=generator)
        for off in range(0,len(y),cfg['batch_size']):
            ids=order[off:off+cfg['batch_size']];xb=x[ids]
            if config['augment']:
                xb=augment(xb)
            opt.zero_grad(set_to_none=True)
            logits=model(xb,rr[ids]);loss=nn.functional.cross_entropy(logits,y[ids],weight=weights)
            if not torch.isfinite(loss):
                raise ValueError('非有限损失')
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True);opt.step()
            total+=float(loss.detach())*len(ids)
        metrics,vl,_=evaluate(model,val)
        row={'candidate':config['id'],'epoch':epoch,'weighted_train_loss':total/len(y),
             'validation_macro_f1':metrics['macro_f1'],'validation_loss':vl,'validation_recall':metrics['recall'],
             'validation_f1':metrics['f1'],'seconds':time.perf_counter()-start}
        with (out/'epochs.jsonl').open('a',encoding='utf-8') as log:
            log.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
        if metrics['macro_f1']>best+1e-8 or (abs(metrics['macro_f1']-best)<=1e-8 and vl<best_loss):
            best=metrics['macro_f1'];best_loss=vl;best_epoch=epoch;best_metrics=metrics
            torch.save(model.state_dict(),out/'best_weights.pt')
            save_json(out/'best_validation.json',{'epoch':epoch,'metrics':metrics,'loss':vl,'gate':gate(metrics,resources,limits)})
        if epoch>=cfg['minimum_epochs'] and epoch-best_epoch>=cfg['patience']:
            break
    model.load_state_dict(torch.load(out/'best_weights.pt',weights_only=True))
    metrics,_,_=evaluate(model,train)
    save_json(out/'train_metrics.json',metrics)
    return {'config':config,'resources':resources,'best_epoch':best_epoch,'epochs':epoch,
            'validation':json.loads((out/'best_validation.json').read_text()),'train':metrics,'weights_sha256':digest(out/'best_weights.pt')}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--protocol',type=Path,default=ROOT/'data/cnn_refined_v3_protocol.json')
    args=ap.parse_args();p=json.loads(args.protocol.read_text(encoding='utf-8'))
    out=args.output_dir
    if out.exists():
        raise FileExistsError('不覆盖实验')
    out.mkdir(parents=True);torch.set_num_threads(p['training']['cpu_threads']);torch.use_deterministic_algorithms(True)
    cache=json.loads((args.cache_dir/'manifest.json').read_text(encoding='utf-8'))
    if digest(args.cache_dir/'protocol.json')!=cache['protocol_sha256']:
        raise ValueError('缓存原始协议变化')
    orig=json.loads((args.cache_dir/'protocol.json').read_text())
    subjects=[orig['subject_alias'].get(r,r) for records in orig['records'].values() for r in records]
    if len(subjects)!=len(set(subjects)):
        raise ValueError('受试者交叉')
    _,train=load_split(args.cache_dir,'train',cache);_,val=load_split(args.cache_dir,'validation',cache)
    mean=train[1].mean(dim=0);std=train[1].std(dim=0,correction=0).clamp_min(.01)
    normalization={'rr_mean':mean.tolist(),'rr_std':std.tolist(),'clip':[-5,5],'fitted_split':'train'}
    train=(train[0],((train[1]-mean)/std).clamp(-5,5),train[2])
    val=(val[0],((val[1]-mean)/std).clamp(-5,5),val[2])
    sources=['data/train_cnn_refined.py','data/train_cnn_candidates.py','src/reference/ecg_trainable_cnn.py','src/reference/ecg_mf_cnn.py']
    meta={'protocol_sha256':digest(args.protocol),'cache_protocol_sha256':cache['protocol_sha256'],
          'source_sha256':{f:digest(ROOT/f) for f in sources},'environment':{'python':platform.python_version(),'torch':torch.__version__,'numpy':np.__version__},
          'source_data_sha256':cache['source_data_sha256'],'cached_data':cache['data'],
          'normalization':normalization,'test_semantics':'KNOWN_DATA_EXPLORATORY_REPLAY','smoke_board_test':'NOT_TESTED'}
    (out/'protocol.json').write_bytes(args.protocol.read_bytes());save_json(out/'manifest_start.json',meta);save_json(out/'normalization.json',normalization)
    for f in sources:
        dst=out/'source_snapshot'/f;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((ROOT/f).read_bytes())
    results=[]
    for config in p['candidates']:
        dst=out/config['id'];dst.mkdir()
        results.append(fit(config,p['training'],train,val,normalization,dst,p['gate']))
        save_json(out/'candidate_summary.json',results)
    chosen=max(results,key=lambda r:(r['validation']['metrics']['macro_f1'],-r['validation']['loss']))
    save_json(out/'selection_before_test.json',chosen)
    model=construct(chosen['config']);model.load_state_dict(torch.load(out/chosen['config']['id']/'best_weights.pt',weights_only=True))
    final={}
    for split in ('train','validation','test'):
        arrays,tensors=load_split(args.cache_dir,split,cache)
        tensors=(tensors[0],((tensors[1]-mean)/std).clamp(-5,5),tensors[2])
        metrics,_,pred=evaluate(model,tensors)
        metrics['per_record']={r:scores(arrays['y'][arrays['record']==r],pred[arrays['record']==r]) for r in sorted(set(arrays['record']))}
        save_json(out/f'{split}_metrics.json',metrics)
        np.savez_compressed(out/f'{split}_predictions.npz',prediction=pred,true=arrays['y'],record=arrays['record'],r_index=arrays['r_index'])
        final[split]={'macro_f1':metrics['macro_f1'],'accuracy':metrics['accuracy'],'f1':metrics['f1'],'recall':metrics['recall'],'gate':gate(metrics,chosen['resources'],p['gate'])}
    meta.update(candidates=results,selected_candidate=chosen['config']['id'],final=final);save_json(out/'manifest.json',meta)
    print(json.dumps({'selected':meta['selected_candidate'],'final':final}),flush=True)


if __name__=='__main__':
    main()
