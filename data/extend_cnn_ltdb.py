"""长程ECG辅助训练：保留v6患者角色/测试字节，未知标定数据显式按ADC归一化。"""
import argparse
from collections import Counter,deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import wfdb

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data'))
from download_external_ecg import retrieve, retrieve_waveform, checksum_map
from prepare_cnn_expanded import LABELS, BEATS, validate_splits, common_window, causal_rr, save, digest


def metadata(raw):
    raw.mkdir(parents=True,exist_ok=True)
    base='https://physionet.org/files/ltdb/1.0.0/'
    official=checksum_map(retrieve(raw,'SHA256SUMS.txt',base))
    records=retrieve(raw,'RECORDS',base,official).decode().split()
    def one(record):
        for ext in ('hea','atr'):retrieve(raw,record+'.'+ext,base,official)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(one,records))
    print(json.dumps({'database':'ltdb','stage':'metadata','verified_records':len(records)}),flush=True)


def freeze(raw,protocol):
    base=ROOT/'data/cnn_expanded_v6_protocol.json'
    p=json.loads(base.read_text(encoding='utf-8'))
    p['version']='cnn_expanded_ltdb_v7_20261017'
    p['parent_protocol_sha256']=digest(base)
    p['old_data_policy']+=' v6 validation is now known development validation; original6 test patients retained unused.'
    p['ltdb']={'source':'https://physionet.org/content/ltdb/1.0.0/', 'license':'ODC Attribution v1.0',
               'identity':'No verified patient mapping, whole source train-only unknown identity group; no claim7 distinct patients or6 new F subjects.',
               'lead':'ECG1, anatomical location unknown',
               'units':'ADC counts; raw header gain0 means uncalibrated. WFDB parser substitutes200; do NOT treat substituted value as known mV.',
               'std_floor_adc':1.0,'caps_per_record_class':[200,1500,1500,1500],
               'sampling':'Choose eligible annotated beats by deterministic hash before waveform extraction; preserve RR history of ALL beat annotations; caps only auxiliary TRAIN'}
    official=checksum_map((raw/'SHA256SUMS.txt').read_bytes())
    for record in (raw/'RECORDS').read_text().split():
        h=wfdb.rdheader(str(raw/record))
        row={'database':'ltdb','record':record,'subject':'ltdb:identity_unknown_pool','lead':'ECG1','fs':h.fs}
        if row['lead'] not in h.sig_name:
            raise ValueError('缺辅助导联')
        for ext in ('hea','atr'):
            f=raw/(record+'.'+ext)
            if digest(f)!=official[f.name]:raise ValueError('LTDB元数据校验错误')
            p['metadata_sha256']['ltdb/'+f.name]=digest(f)
        p['splits']['train'].append(row)
    validate_splits(p['splits'])
    p['candidates']=[dict(c,id=c['id'].replace('expanded_','ltdb_')) for c in p['candidates']]
    p['gate']['scope']='Same assistant engineering thresholds on known development validation and one fresh patient-held-out test; no competition/clinical claim.'
    p['scope']='expert-centered mixed-source training with INCART held-out patients; training also contains INCART, not whole-source external validation'
    p['test_policy']='Do not evaluate test unless validation-selected candidate passes unchanged validation gate. Test patients and bytes identical to v6, never used for training/selection. If failed, keep test unused.'
    p['sources'].append(p['ltdb']['source'])
    save(protocol,p)
    print(json.dumps({'frozen':str(protocol),'sha256':digest(protocol),'parent_sha256':digest(base)}),flush=True)


def download(raw,protocol):
    p=json.loads(protocol.read_text(encoding='utf-8'));official=checksum_map((raw/'SHA256SUMS.txt').read_bytes())
    records=[r['record'] for r in p['splits']['train'] if r['database']=='ltdb']
    def one(record):retrieve_waveform(raw,record+'.dat','https://archive.physionet.org/physiobank/database/ltdb/',official)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(one,records))
    print(json.dumps({'database':'ltdb','stage':'waveforms','verified_files':len(records)}),flush=True)


def selected_beats(ann,length,fs,p,record):
    mapping={s:i for i,ss in enumerate(LABELS.values()) for s in ss}
    import math
    before=math.ceil(fs*p['window']['before_seconds']);after=math.ceil(fs*p['window']['after_seconds'])
    rows=[];history=deque(maxlen=401);previous=None;excluded=Counter()
    for index,symbol in zip(ann.sample,ann.symbol):
        index=int(index)
        if symbol not in BEATS:continue
        if previous is None:
            previous=index;excluded['first_beat_no_rr']+=1;continue
        delta=index-previous;previous=index
        if delta<=0:raise ValueError('LTDB非正RR')
        history.append(delta/fs)
        if symbol not in mapping:
            excluded['unmapped_'+symbol]+=1;continue
        if index<before or index+after>length:
            excluded['incomplete_window']+=1;continue
        rows.append((index,mapping[symbol],symbol,causal_rr(list(history))))
    chosen=[]
    for cls,cap in enumerate(p['ltdb']['caps_per_record_class']):
        eligible=[r for r in rows if r[1]==cls]
        ranked=sorted(eligible,key=lambda r:hashlib.sha256(f"{p['train_sampling']['seed']}:ltdb:{record}:{r[0]}".encode()).digest())
        chosen.extend(ranked[:cap])
    return sorted(chosen,key=lambda r:r[0]),dict(excluded),Counter(r[1] for r in rows)


def prepare(raw,parent,protocol,out):
    p=json.loads(protocol.read_text(encoding='utf-8'));old=json.loads((parent/'manifest.json').read_text(encoding='utf-8'))
    if digest(parent/'protocol.json')!=p['parent_protocol_sha256'] or old['protocol_sha256']!=p['parent_protocol_sha256']:
        raise ValueError('父缓存协议不符')
    validate_splits(p['splits'])
    if out.exists():raise FileExistsError('不覆盖扩展缓存')
    out.mkdir(parents=True);shutil.copyfile(protocol,out/'protocol.json')
    manifest=json.loads(json.dumps(old));manifest['protocol_sha256']=digest(protocol)
    manifest['parent_cache_manifest_sha256']=digest(parent/'manifest.json')
    manifest['parent_train_counts']=old['data']['train']['class_counts']
    manifest['identity_unknown_sources']=['svdb','ltdb']
    for role in ('train','validation','test'):
        if digest(parent/(role+'.npz'))!=old['data'][role]['file_sha256']:
            raise ValueError('父数据变化')
    for role in ('validation','test'):
        shutil.copyfile(parent/(role+'.npz'),out/(role+'.npz'))
        if digest(out/(role+'.npz'))!=old['data'][role]['file_sha256']:raise ValueError('复制后字节不同')
    official=checksum_map((raw/'SHA256SUMS.txt').read_bytes())
    lists={k:[] for k in ('x','rr','y','record','subject','r_index','code','sampling_unit')}
    record_info={}
    for row in p['splits']['train']:
        if row['database']!='ltdb':continue
        record=row['record'];key='ltdb:'+record
        hashes={}
        for ext in ('dat','hea','atr'):
            f=raw/(record+'.'+ext);hashes[ext]=digest(f)
            if hashes[ext]!=official[f.name]:raise ValueError('LTDB官方SHA错误')
            if ext!='dat' and hashes[ext]!=p['metadata_sha256']['ltdb/'+f.name]:raise ValueError('冻结后LTDB标注变化')
        manifest['source_data_sha256'][key]=hashes
        h=wfdb.rdheader(str(raw/record));ch=h.sig_name.index(row['lead'])
        if h.fs!=row['fs']:raise ValueError('LTDB采样率变化')
        ann=wfdb.rdann(str(raw/record),'atr')
        chosen,excluded,original=selected_beats(ann,h.sig_len,h.fs,p,record)
        d=wfdb.rdrecord(str(raw/record),channels=[ch],physical=False).d_signal[:,0]
        if int(d[0])!=h.init_value[ch] or (int(d.astype(np.int64).sum())-h.checksum[ch])%65536:raise ValueError('LTDB首值/校验和错误')
        # 不使用WFDB为gain0代填的200；只归一化ADC形态，不能还原人体电压。
        signal=d.astype(np.float64)
        cfg=dict(p['window'],std_floor_mv=p['ltdb']['std_floor_adc'])
        # 公共函数内部std_floor_mv是历史参数名，此处输入/下限均为ADC，不称mV。
        counts=Counter()
        for index,cls,symbol,rr in chosen:
            x=common_window(signal,index,h.fs,cfg)
            if x is None:raise ValueError('已选完整窗口丢失')
            sample={'x':x,'rr':rr,'y':cls,'record':key,'subject':'ltdb:identity_unknown_pool',
                    'r_index':index,'code':symbol,'sampling_unit':key}
            for k,v in sample.items():lists[k].append(v)
            counts[cls]+=1
        record_info[key]={'before_cap':[original[i] for i in range(4)],'after_cap':[counts[i] for i in range(4)],
                          'excluded':excluded,'units':'uncalibrated ADC normalized per beat','lead':row['lead']}
        print(json.dumps({'record':key,**record_info[key]}),flush=True)
    original=dict(np.load(parent/'train.npz',allow_pickle=False))
    arrays={}
    for k in original:
        dtype=np.float32 if k in ('x','rr') else (np.int64 if k in ('y','r_index') else None)
        arrays[k]=np.concatenate([original[k],np.asarray(lists[k],dtype=dtype)],axis=0)
    np.savez_compressed(out/'train.npz',**arrays)
    info=manifest['data']['train'];info['examples']=len(arrays['y']);info['class_counts']=np.bincount(arrays['y'],minlength=4).tolist()
    info['file_sha256']=digest(out/'train.npz');info['ltdb_per_record']=record_info
    # 不将未知身份组算入“可确认患者数”。父缓存的24名F患者等数量保持不变。
    info['class_verified_subject_counts']=old['data']['train']['class_verified_subject_counts']
    info['before_train_cap']=[old['data']['train']['before_train_cap'][i]+sum(r['before_cap'][i] for r in record_info.values()) for i in range(4)]
    manifest['source_sha256']['data/extend_cnn_ltdb.py']=digest(Path(__file__))
    for f in manifest['source_sha256']:
        dst=out/'source_snapshot'/f;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/f,dst)
    manifest['auxiliary_units_caveat']=p['ltdb']['units']
    save(out/'manifest.json',manifest)
    print(json.dumps({'train_counts':info['class_counts'],'examples':info['examples'],'validation_test_identical_to_v6':True}),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('stage',choices=['metadata','freeze','download','prepare'])
    ap.add_argument('--raw-dir',type=Path,required=True);ap.add_argument('--protocol',type=Path,required=True)
    ap.add_argument('--parent-cache',type=Path);ap.add_argument('--output-dir',type=Path)
    args=ap.parse_args()
    if args.stage=='metadata':metadata(args.raw_dir)
    elif args.stage=='freeze':freeze(args.raw_dir,args.protocol)
    elif args.stage=='download':download(args.raw_dir,args.protocol)
    else:
        if args.parent_cache is None or args.output_dir is None:ap.error('prepare需要parent-cache与output-dir')
        prepare(args.raw_dir,args.parent_cache,args.protocol,args.output_dir)
