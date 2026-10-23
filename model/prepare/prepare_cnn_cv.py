"""只在26名已知开发患者中冻结三折；原6名测试患者完全排除。"""
import argparse
from collections import Counter,defaultdict,deque
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import wfdb

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'data'))
sys.path.insert(0,str(ROOT/'model/prepare'))
from prepare_cnn_expanded import LABELS,BEATS,common_window,causal_rr,save,digest
from download_external_ecg import checksum_map


def validate_folds(folds,heldout):
    flat=[s for group in folds for s in group]
    if len(flat)!=len(set(flat)) or set(flat)&set(heldout):
        raise ValueError('开发折重复或进入独立测试患者')


def freeze(parent_path,parent_cache,out):
    p=json.loads(parent_path.read_text(encoding='utf-8'))
    rows=[r for role in ('train','validation') for r in p['splits'][role] if r['database']=='incartdb']
    counts=defaultdict(lambda:np.zeros(4))
    for row in rows:counts[row['subject']]+=[row['counts'][k] for k in LABELS]
    names=sorted(counts);matrix=np.array([counts[s] for s in names]);rng=np.random.default_rng(2026101708)
    best=None;target=np.array([9,9,8])/26
    for _ in range(20000):
        perm=rng.permutation(len(names));groups=[perm[:9],perm[9:18],perm[18:]]
        sums=np.array([matrix[g].sum(0) for g in groups]);present=np.array([(matrix[g]>0).sum(0) for g in groups])
        if np.any(present[:,1]<3) or np.any(present[:,3]<3) or np.any(sums[:,1]<100):continue
        cost=float(np.square(sums/matrix.sum(0)-target[:,None]).sum())
        if best is None or cost<best[0]:best=(cost,groups)
    if best is None:raise ValueError('三折标注支持不足，不自动放松条件')
    folds=[[names[i] for i in group] for group in best[1]]
    heldout=sorted({r['subject'] for r in p['splits']['test']});validate_folds(folds,heldout)
    original=json.loads((parent_cache/'manifest.json').read_text(encoding='utf-8'))
    protocol={'version':'cnn_patient_cv_v8_20261017','classes':list(LABELS),'label_symbols':LABELS,
              'parent_protocol_sha256':digest(parent_path),'parent_cache_manifest_sha256':digest(parent_cache/'manifest.json'),
              'parent_cache_train_sha256':original['data']['train']['file_sha256'],
              'development_records':rows,'folds':folds,'excluded_independent_test_subjects':heldout,
              'fold_design':{'seed':2026101708,'draws':20000,'subject_counts':[9,9,8],'minimum_S_F_subjects_each':3,'minimum_S_beats_each':100,'annotation_only_cost':best[0]},
              'window':p['window'],'train_sampling':p['train_sampling'],
              'gate':p['gate'],'training':{'seed':2026101708,'cpu_threads':4,'batch_size':256,
                     'max_epochs':50,'minimum_epochs':25,'patience':10,'learning_rate':.001,'weight_decay':.001,
                     'scheduler':'CosineAnnealingLR T_max50 eta_min1e-5','class_weight_power':.5,
                     'selection':'mean of3 fold validation macro-F1; tie lower mean validation CE; no independent test access'},
              'candidates':[{'id':f'{family}_{source}','family':family,'sources':source} for family in ('residual','temporal') for source in ('verified','all')],
              'source_policy':'verified includes MIT known-development MLII + INCART II; all adds SVDB ECG1 and LTDB uncalibrated-ADC ECG1. Auxiliary identities unknown train-only, not verified patient counts.',
              'evaluation':'Each fold validation INCART subjects held out from that fit; natural prevalence, no cap. Training caps applied inside each fold only. All26 patients previously used for development, OOF is development cross-validation, not a fresh independent test.',
              'test_policy':'Do not load or evaluate independent6 patients in this script. Any later final fit/test requires explicit frozen procedure after CV passes; do not treat an individual fold model as full-data final.',
              'smoke_board_test':'NOT_TESTED'}
    protocol['gate']['scope']='Unchanged assistant engineering gate on pooled development OOF and each fold; not clinical or competition standard.'
    save(out,protocol);print(json.dumps({'protocol':str(out),'sha256':digest(out),'folds':folds,'test_excluded':heldout}),flush=True)


def prepare(raw,parent,protocol,out):
    p=json.loads(protocol.read_text(encoding='utf-8'));validate_folds(p['folds'],p['excluded_independent_test_subjects'])
    if out.exists():raise FileExistsError('不覆盖开发缓存')
    if digest(parent/'manifest.json')!=p['parent_cache_manifest_sha256']:raise ValueError('父缓存清单变更')
    if digest(parent/'train.npz')!=p['parent_cache_train_sha256']:raise ValueError('辅助训练缓存变更')
    out.mkdir(parents=True);shutil.copyfile(protocol,out/'protocol.json')
    # 仅复用父TRAIN的非INCART部分；不读取其test.npz。
    z=dict(np.load(parent/'train.npz',allow_pickle=False));mask=np.array([not r.startswith('incartdb:') for r in z['record']])
    np.savez_compressed(out/'auxiliary.npz',**{k:v[mask] for k,v in z.items()})
    mapping={s:i for i,ss in enumerate(LABELS.values()) for s in ss};lists=defaultdict(list);excluded=Counter();sources={}
    directory=raw/'incartdb';official=checksum_map((directory/'SHA256SUMS.txt').read_bytes())
    for row in p['development_records']:
        record=row['record'];key='incartdb:'+record
        for ext in ('dat','hea','atr'):
            f=directory/(record+'.'+ext)
            if digest(f)!=official[f.name]:raise ValueError('官方原始数据SHA错误')
            sources['incartdb/'+f.name]=digest(f)
        h=wfdb.rdheader(str(directory/record));ch=h.sig_name.index('II')
        if h.fs!=row['fs'] or h.units[ch]!='mV':raise ValueError('INCART参数变化')
        if 'patient '+row['subject'].split(':')[1] not in h.comments:raise ValueError('患者身份冲突')
        d=wfdb.rdrecord(str(directory/record),channels=[ch],physical=False).d_signal[:,0]
        if int(d[0])!=h.init_value[ch] or (int(d.astype(np.int64).sum())-h.checksum[ch])%65536:raise ValueError('首值/校验和错误')
        signal=(d.astype(np.float64)-h.baseline[ch])/h.adc_gain[ch]
        ann=wfdb.rdann(str(directory/record),'atr');previous=None;history=deque(maxlen=401);n=0
        for index,symbol in zip(ann.sample,ann.symbol):
            index=int(index)
            if symbol not in BEATS:continue
            if previous is None:previous=index;excluded['first_beat_no_rr']+=1;continue
            delta=index-previous;previous=index
            if delta<=0:raise ValueError('非正RR')
            history.append(delta/h.fs)
            if symbol not in mapping:excluded['unmapped_'+symbol]+=1;continue
            x=common_window(signal,index,h.fs,p['window'])
            if x is None:excluded['incomplete_window']+=1;continue
            row_values={'x':x,'rr':causal_rr(list(history)),'y':mapping[symbol],'record':key,'subject':row['subject'],'r_index':index,'code':symbol,'sampling_unit':row['subject']}
            for k,v in row_values.items():lists[k].append(v)
            n+=1
        print(json.dumps({'record':key,'examples':n}),flush=True)
    arrays={k:np.asarray(v,dtype=np.float32 if k in ('x','rr') else (np.int64 if k in ('y','r_index') else None)) for k,v in lists.items()}
    assert set(arrays['subject'])==set(s for f in p['folds'] for s in f)
    np.savez_compressed(out/'development.npz',**arrays)
    manifest={'protocol_sha256':digest(protocol),'development_sha256':digest(out/'development.npz'),'auxiliary_sha256':digest(out/'auxiliary.npz'),
              'development_examples':len(arrays['y']),'development_counts':np.bincount(arrays['y'],minlength=4).tolist(),
              'source_data_sha256':sources,'excluded':dict(excluded),'test_access':'NOT_LOADED','smoke_board_test':'NOT_TESTED'}
    manifest['source_sha256']={}
    for file in ('model/prepare/prepare_cnn_cv.py','model/prepare/prepare_cnn_expanded.py','model/prepare/download_external_ecg.py'):
        dst=out/'source_snapshot'/file;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/file,dst);manifest['source_sha256'][file]=digest(ROOT/file)
    save(out/'manifest.json',manifest);print(json.dumps({k:v for k,v in manifest.items() if k not in ('source_data_sha256','source_sha256')}),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('stage',choices=['freeze','prepare']);ap.add_argument('--protocol',type=Path,required=True)
    ap.add_argument('--parent-protocol',type=Path,default=ROOT/'model/protocols/cnn_expanded_v7_protocol.json');ap.add_argument('--parent-cache',type=Path,required=True)
    ap.add_argument('--raw-dir',type=Path);ap.add_argument('--output-dir',type=Path);a=ap.parse_args()
    if a.stage=='freeze':freeze(a.parent_protocol,a.parent_cache,a.protocol)
    else:
        if a.raw_dir is None or a.output_dir is None:ap.error('prepare需要raw-dir和output-dir')
        prepare(a.raw_dir,a.parent_cache,a.protocol,a.output_dir)
