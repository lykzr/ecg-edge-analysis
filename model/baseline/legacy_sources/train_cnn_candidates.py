"""可训练轻量CNN候选训练；全部选型仅看训练/验证，最后一次已查看测试回放。"""
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


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save_json(p,value):
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def gate(metrics,resources,limits):
    reasons=[]
    if metrics['macro_f1']<limits['macro_f1']:
        reasons.append('macro_f1')
    for i,name in enumerate(('N','S','V','F')):
        if metrics['f1'][i]<limits['minimum_class_f1']:
            reasons.append(name+'_f1')
        if metrics['recall'][i]<limits['recall'][i]:
            reasons.append(name+'_recall')
    if resources['trainable_parameters']>limits['maximum_parameters']:
        reasons.append('parameter_budget')
    return {'passed':not reasons,'failed_checks':reasons}


def load_split(folder,split,manifest):
    path=folder/f'{split}.npz'
    if digest(path)!=manifest['data'][split]['file_sha256']:
        raise ValueError('已有缓存哈希变化：'+split)
    arrays=dict(np.load(path,allow_pickle=False))
    length=manifest.get('input_samples',64)
    if arrays['x'].shape!=(len(arrays['y']),length) or arrays['rr'].shape!=(len(arrays['y']),3):
        raise ValueError('输入维度不符')
    if not np.isfinite(arrays['x']).all() or not np.isfinite(arrays['rr']).all():
        raise ValueError('输入有非有限数')
    return arrays,tuple(torch.from_numpy(arrays[k]) for k in ('x','rr','y'))


@torch.no_grad()
def evaluate(model,tensors,batch_size=2048):
    model.eval();x,rr,y=tensors;outputs=[];loss=0.
    for i in range(0,len(y),batch_size):
        logits=model(x[i:i+batch_size],rr[i:i+batch_size])
        outputs.append(logits.argmax(dim=1).numpy())
        loss+=nn.functional.cross_entropy(logits,y[i:i+batch_size],reduction='sum').item()
    prediction=np.concatenate(outputs)
    return scores(y.numpy(),prediction),loss/len(y),prediction


def train_candidate(config,cfg,train,val,out,limits):
    seed=cfg['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    model=create_model(config);resources=budget(model)
    if resources['trainable_parameters']>limits['maximum_parameters']:
        raise ValueError('候选超过参数预算')
    opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
    x,rr,y=train;counts=torch.bincount(y,minlength=4)
    sampling_weights=1/counts[y].double()
    generator=torch.Generator().manual_seed(seed)
    best=-1.;best_loss=float('inf');best_epoch=0;history=[]
    for epoch in range(1,cfg['max_epochs']+1):
        start=time.perf_counter();model.train();loss_sum=0.
        indices=torch.multinomial(sampling_weights,len(y),replacement=True,generator=generator)
        for i in range(0,len(y),cfg['batch_size']):
            ids=indices[i:i+cfg['batch_size']]
            opt.zero_grad(set_to_none=True)
            logits=model(x[ids],rr[ids]);loss=nn.functional.cross_entropy(logits,y[ids])
            if not torch.isfinite(loss):
                raise ValueError('训练损失非有限')
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True);opt.step()
            loss_sum+=float(loss.detach())*len(ids)
        metrics,vl,_=evaluate(model,val)
        row={'candidate':config['id'],'epoch':epoch,'balanced_train_loss':loss_sum/len(y),'validation_loss':vl,
             'validation_macro_f1':metrics['macro_f1'],'validation_recall':metrics['recall'],
             'validation_f1':metrics['f1'],'seconds':time.perf_counter()-start}
        history.append(row)
        with (out/'epochs.jsonl').open('a',encoding='utf-8') as log:
            log.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
        if metrics['macro_f1']>best+1e-8 or (abs(metrics['macro_f1']-best)<=1e-8 and vl<best_loss):
            best=metrics['macro_f1'];best_loss=vl;best_epoch=epoch
            torch.save(model.state_dict(),out/'best_weights.pt')
            save_json(out/'best_validation.json',{'epoch':epoch,'metrics':metrics,'loss':vl,'gate':gate(metrics,resources,limits)})
        if epoch>=cfg['minimum_epochs'] and epoch-best_epoch>=cfg['patience']:
            break
    return {'config':config,'best_epoch':best_epoch,'epochs':len(history),'resources':resources,
            'validation':json.loads((out/'best_validation.json').read_text(encoding='utf-8')),
            'weights_sha256':digest(out/'best_weights.pt')}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--protocol',type=Path,default=ROOT/'data/cnn_trainable_v2_protocol.json')
    args=ap.parse_args();cfg=json.loads(args.protocol.read_text(encoding='utf-8'))
    if args.output_dir.exists():
        raise FileExistsError('输出已存在，不覆盖实验')
    args.output_dir.mkdir(parents=True);out=args.output_dir
    torch.set_num_threads(cfg['training']['cpu_threads']);torch.use_deterministic_algorithms(True)
    cache=json.loads((args.cache_dir/'manifest.json').read_text(encoding='utf-8'))
    original=json.loads((args.cache_dir/'protocol.json').read_text(encoding='utf-8'))
    if digest(args.cache_dir/'protocol.json')!=cache['protocol_sha256']:
        raise ValueError('缓存数据协议变化')
    subjects=[original['subject_alias'].get(r,r) for records in original['records'].values() for r in records]
    if len(subjects)!=len(set(subjects)):
        raise ValueError('缓存存在受试者交叉')
    source_files=['data/train_cnn_candidates.py','src/reference/ecg_trainable_cnn.py','src/reference/ecg_mf_cnn.py']
    meta={'environment':{'python':platform.python_version(),'torch':torch.__version__,'numpy':np.__version__,
                         'cpu_threads':torch.get_num_threads(),'deterministic':True},
          'protocol_sha256':digest(args.protocol),'data_protocol_sha256':cache['protocol_sha256'],
          'cached_data_hashes':cache['data'],'source_sha256':{p:digest(ROOT/p) for p in source_files},
          'source_data_sha256':cache['source_data_sha256'],'test_semantics':'KNOWN_DATA_EXPLORATORY_REPLAY_AFTER_V1',
          'smoke_board_test':'NOT_TESTED','quantization':'NOT_IMPLEMENTED'}
    (out/'protocol.json').write_bytes(args.protocol.read_bytes())
    snap=out/'source_snapshot'
    for name in source_files:
        dest=snap/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
    save_json(out/'manifest_start.json',meta)
    # 此处只加载训练/验证。最后才读取测试缓存，杜绝逐候选偷看测试成绩。
    tr_arrays,train=load_split(args.cache_dir,'train',cache)
    va_arrays,val=load_split(args.cache_dir,'validation',cache)
    candidates=[]
    for candidate in cfg['candidates']:
        path=out/candidate['id'];path.mkdir()
        result=train_candidate(candidate,cfg['training'],train,val,path,cfg['gate'])
        candidates.append(result);save_json(out/'candidate_summary.json',candidates)
    selected=max(candidates,key=lambda r:(r['validation']['metrics']['macro_f1'],-r['validation']['loss']))
    # 将选择结果落盘后才打开测试；回放失败也不改选其它候选。
    save_json(out/'selection_before_test.json',selected)
    model=create_model(selected['config'])
    model.load_state_dict(torch.load(out/selected['config']['id']/'best_weights.pt',map_location='cpu',weights_only=True))
    final={}
    for split in ('train','validation','test'):
        arrays,tensors=load_split(args.cache_dir,split,cache)
        metrics,loss,pred=evaluate(model,tensors)
        metrics['per_record']={r:scores(arrays['y'][arrays['record']==r],pred[arrays['record']==r]) for r in sorted(set(arrays['record']))}
        save_json(out/f'{split}_metrics.json',metrics)
        np.savez_compressed(out/f'{split}_predictions.npz',true=arrays['y'],prediction=pred,record=arrays['record'],r_index=arrays['r_index'])
        final[split]={'macro_f1':metrics['macro_f1'],'accuracy':metrics['accuracy'],'recall':metrics['recall'],
                      'f1':metrics['f1'],'gate':gate(metrics,selected['resources'],cfg['gate'])}
    meta.update(candidates=candidates,selected_candidate=selected['config']['id'],final=final)
    save_json(out/'manifest.json',meta)
    print(json.dumps({'selected':meta['selected_candidate'],'final':final},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
