"""三折患者级开发验证与来源消融；不提供独立测试读取入口。"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import shutil
import sys
import time

import numpy as np
import torch
from torch import nn

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_mf_cnn import scores
from ecg_trainable_cnn import budget
from ecg_temporal_cnn import TemporalCnn
from train_cnn_candidates import digest,save_json,evaluate,gate
from train_cnn_refined import construct,augment

SOURCES=['data/train_cnn_cv.py','data/train_cnn_candidates.py','data/train_cnn_refined.py',
         'src/reference/ecg_temporal_cnn.py','src/reference/ecg_trainable_cnn.py','src/reference/ecg_mf_cnn.py']


def cap_training(arrays,seed,caps):
    chosen=[]
    for subject in sorted(set(arrays['subject'])):
        for cls,limit in enumerate(caps):
            ids=np.flatnonzero((arrays['subject']==subject)&(arrays['y']==cls))
            ids=sorted(ids,key=lambda i:hashlib.sha256(f"{seed}:{arrays['record'][i]}:{arrays['r_index'][i]}".encode()).digest())
            chosen.extend(ids[:limit])
    indices=np.array(sorted(chosen),dtype=np.int64)
    return {k:v[indices] for k,v in arrays.items()}


def make_model(config):
    if config['family']=='temporal':return TemporalCnn(16)
    return construct({'family':'residual','feature':'both','width':16,'input_samples':128,'batch_norm':'none'})


def split_arrays(dev,aux,subjects,config,p):
    validation=np.isin(dev['subject'],subjects)
    train=cap_training({k:v[~validation] for k,v in dev.items()},p['train_sampling']['seed'],p['train_sampling']['per_verified_subject_per_class'])
    use=np.ones(len(aux['y']),dtype=bool) if config['sources']=='all' else np.array([r.startswith('mitdb:') for r in aux['record']])
    train={k:np.concatenate([v,aux[k][use]]) for k,v in train.items()}
    val={k:v[validation] for k,v in dev.items()}
    if set(train['subject'])&set(val['subject']):raise ValueError('同人跨训练/验证')
    forbidden=set(p['excluded_independent_test_subjects'])
    if (set(train['subject'])|set(val['subject']))&forbidden:raise ValueError('独立测试进入开发')
    for group in (train,val):
        if not np.all(np.bincount(group['y'],minlength=4)>0):raise ValueError('缺类别，不自动删类')
    return train,val


def tensors(arrays,norm=None):
    x=torch.from_numpy(arrays['x']);rr=torch.from_numpy(arrays['rr']);y=torch.from_numpy(arrays['y'])
    if norm is None:
        norm={'rr_mean':rr.mean(0).tolist(),'rr_std':rr.std(0,correction=0).clamp_min(.01).tolist(),'fitted_role':'fold_train'}
    rr=((rr-torch.tensor(norm['rr_mean']))/torch.tensor(norm['rr_std'])).clamp(-5,5)
    return (x,rr,y),norm


def fit(config,p,fold,train,val,out):
    cfg=p['training'];seed=cfg['seed']+fold;random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    model=make_model(config);resources=budget(model)
    tr,norm=tensors(train);va,_=tensors(val,norm);save_json(out/'normalization.json',norm)
    n=torch.bincount(tr[2],minlength=4);weights=(len(tr[2])/(4*n.float()))**cfg['class_weight_power'];weights/=weights.mean()
    opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=cfg['max_epochs'],eta_min=1e-5)
    generator=torch.Generator().manual_seed(seed);best=-1.;best_loss=float('inf');best_epoch=0
    for epoch in range(1,cfg['max_epochs']+1):
        start=time.perf_counter();model.train();order=torch.randperm(len(tr[2]),generator=generator);loss_total=0.
        for offset in range(0,len(order),cfg['batch_size']):
            ids=order[offset:offset+cfg['batch_size']];x=augment(tr[0][ids])
            opt.zero_grad(set_to_none=True);logits=model(x,tr[1][ids])
            loss=nn.functional.cross_entropy(logits,tr[2][ids],weight=weights)
            if not torch.isfinite(loss):raise ValueError('非有限损失')
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True);opt.step()
            loss_total+=float(loss.detach())*len(ids)
        metric,vl,pred=evaluate(model,va)
        row={'candidate':config['id'],'fold':fold,'epoch':epoch,'learning_rate':opt.param_groups[0]['lr'],
             'train_weighted_loss':loss_total/len(order),'validation_macro_f1':metric['macro_f1'],
             'validation_loss':vl,'validation_recall':metric['recall'],'validation_f1':metric['f1'],
             'seconds':time.perf_counter()-start}
        with (out/'epochs.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
        if metric['macro_f1']>best+1e-8 or (abs(metric['macro_f1']-best)<=1e-8 and vl<best_loss):
            best=metric['macro_f1'];best_loss=vl;best_epoch=epoch;torch.save(model.state_dict(),out/'best_weights.pt')
            save_json(out/'best_validation.json',{'epoch':epoch,'metrics':metric,'loss':vl,'gate':gate(metric,resources,p['gate'])})
        scheduler.step()
        if epoch>=cfg['minimum_epochs'] and epoch-best_epoch>=cfg['patience']:break
    model.load_state_dict(torch.load(out/'best_weights.pt',weights_only=True))
    metric,vl,pred=evaluate(model,va);train_metrics,_,_=evaluate(model,tr)
    metric['per_subject']={s:scores(val['y'][val['subject']==s],pred[val['subject']==s]) for s in sorted(set(val['subject']))}
    save_json(out/'validation_metrics.json',metric);save_json(out/'train_metrics.json',train_metrics)
    np.savez_compressed(out/'validation_predictions.npz',prediction=pred,true=val['y'],subject=val['subject'],record=val['record'],r_index=val['r_index'])
    result={'config':config,'fold':fold,'epochs':epoch,'best_epoch':best_epoch,'resources':resources,
            'validation_macro_f1':metric['macro_f1'],'validation_loss':vl,'validation_gate':gate(metric,resources,p['gate']),
            'validation_support':metric['support'],'train_macro_f1':train_metrics['macro_f1'],
            'train_counts':np.bincount(train['y'],minlength=4).tolist(),'train_subjects':sorted(set(train['subject'])),
            'validation_subjects':sorted(set(val['subject'])),'weights_sha256':digest(out/'best_weights.pt')}
    save_json(out/'result.json',result);return result


def run(cache,protocol,out):
    p=json.loads(protocol.read_text(encoding='utf-8'));m=json.loads((cache/'manifest.json').read_text(encoding='utf-8'))
    if digest(protocol)!=m['protocol_sha256'] or digest(cache/'protocol.json')!=digest(protocol):raise ValueError('协议不匹配')
    for name in ('development','auxiliary'):
        if digest(cache/(name+'.npz'))!=m[name+'_sha256']:raise ValueError('开发缓存变化')
    if out.exists():raise FileExistsError('不覆盖实验')
    out.mkdir(parents=True);shutil.copyfile(protocol,out/'protocol.json')
    start={'protocol_sha256':digest(protocol),'cache_manifest_sha256':digest(cache/'manifest.json'),
           'environment':{'python':platform.python_version(),'torch':torch.__version__,'numpy':np.__version__},
           'source_sha256':{f:digest(ROOT/f) for f in SOURCES},'test_access':'NO_TEST_READER_IN_THIS_SCRIPT','smoke_board_test':'NOT_TESTED'}
    save_json(out/'manifest_start.json',start)
    for file in SOURCES:
        target=out/'source_snapshot'/file;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/file,target)
    dev=dict(np.load(cache/'development.npz',allow_pickle=False));aux=dict(np.load(cache/'auxiliary.npz',allow_pickle=False))
    all_runs=[];summaries=[]
    for config in p['candidates']:
        rows=[];predictions=[];true=[];subjects=[];records=[];indices=[]
        for fold,held in enumerate(p['folds']):
            folder=out/config['id']/f'fold_{fold}';folder.mkdir(parents=True)
            train,val=split_arrays(dev,aux,held,config,p);result=fit(config,p,fold,train,val,folder)
            rows.append(result);all_runs.append(result);save_json(out/'fold_summary.json',all_runs)
            z=np.load(folder/'validation_predictions.npz',allow_pickle=False)
            for values,key in ((predictions,'prediction'),(true,'true'),(subjects,'subject'),(records,'record'),(indices,'r_index')):values.append(z[key])
        y=np.concatenate(true);pred=np.concatenate(predictions);sub=np.concatenate(subjects)
        metric=scores(y,pred);metric['per_subject']={s:scores(y[sub==s],pred[sub==s]) for s in sorted(set(sub))}
        if len(y)!=len(dev['y']):raise ValueError('OOF覆盖数量错误')
        ids=list(zip(np.concatenate(records).tolist(),np.concatenate(indices).tolist()))
        if len(set(ids))!=len(dev['y']):raise ValueError('OOF心拍重复')
        save_json(out/config['id']/'oof_metrics.json',metric)
        np.savez_compressed(out/config['id']/'oof_predictions.npz',true=y,prediction=pred,subject=sub,record=np.concatenate(records),r_index=np.concatenate(indices))
        pooled_gate=gate(metric,rows[0]['resources'],p['gate'])
        summary={'config':config,'mean_fold_macro_f1':float(np.mean([r['validation_macro_f1'] for r in rows])),
                 'mean_fold_loss':float(np.mean([r['validation_loss'] for r in rows])),
                 'fold_macro_f1':[r['validation_macro_f1'] for r in rows],'oof_metrics':metric,
                 'resources':rows[0]['resources'],'pooled_gate':pooled_gate,
                 'accepted':pooled_gate['passed'] and all(r['validation_gate']['passed'] for r in rows)}
        summaries.append(summary);save_json(out/'candidate_summary.json',summaries)
        print(json.dumps({'stage':'candidate_finished','candidate':config['id'],'mean_fold_macro_f1':summary['mean_fold_macro_f1'],'oof_macro_f1':metric['macro_f1'],'accepted':summary['accepted']}),flush=True)
    chosen=max(summaries,key=lambda r:(r['mean_fold_macro_f1'],-r['mean_fold_loss']))
    save_json(out/'decision.json',{'selected':chosen,'accepted':chosen['accepted'],'epochs':sum(r['epochs'] for r in all_runs),
                                 'test_status':'NOT_LOADED','status':'CV_COMPLETED_NO_FINAL_FULL_DATA_MODEL','smoke_board_test':'NOT_TESTED'})
    print(json.dumps({'stage':'complete','selected':chosen['config']['id'],'accepted':chosen['accepted'],'mean_fold_macro_f1':chosen['mean_fold_macro_f1'],'oof_macro_f1':chosen['oof_metrics']['macro_f1']}),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--cache-dir',type=Path,required=True);ap.add_argument('--protocol',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True)
    a=ap.parse_args();p=json.loads(a.protocol.read_text(encoding='utf-8'));torch.set_num_threads(p['training']['cpu_threads']);torch.use_deterministic_algorithms(True)
    run(a.cache_dir,a.protocol,a.output_dir)
