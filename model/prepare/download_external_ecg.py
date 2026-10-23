"""从PhysioNet固定版本获取ECG元数据/按协议波形；官方SHA256校验，不覆盖。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen, Request
import re

ROOT=Path(__file__).resolve().parents[2]
DATABASES=('incartdb','svdb')


def checksum_map(data):
    return {line.split()[1].lstrip('*'):line.split()[0] for line in data.decode().splitlines() if len(line.split())==2}


def retrieve(directory,name,base,official=None):
    path=directory/name
    if path.exists():
        data=path.read_bytes()
    else:
        for attempt in range(4):
            try:
                with urlopen(base+name,timeout=90) as response:
                    data=response.read()
                break
            except Exception:
                if attempt==3:
                    raise
                time.sleep(1+attempt)
        if official is not None and hashlib.sha256(data).hexdigest()!=official[name]:
            raise ValueError('官方SHA256不符：'+name)
        with path.open('xb') as stream:
            stream.write(data)
    if official is not None and hashlib.sha256(data).hexdigest()!=official[name]:
        raise ValueError('已有文件官方SHA256不符，不覆盖：'+str(path))
    return data


def retrieve_waveform(directory,name,base,official):
    """有限大小Range请求；分块可恢复，最终仍只认完整文件官方SHA。"""
    path=directory/name
    if path.exists():
        retrieve(directory,name,base,official)
        return
    parts=directory/('.parts_'+name);parts.mkdir(exist_ok=True)
    offset=0;total=None;chunks=[];size=1024*1024
    while total is None or offset<total:
        end=offset+size-1 if total is None else min(offset+size,total)-1
        chunk=parts/str(offset)
        meta=parts/(str(offset)+'.json')
        if chunk.exists() and meta.exists():
            saved=json.loads(meta.read_text());data=chunk.read_bytes();actual_total=saved['total']
        else:
            for attempt in range(4):
                try:
                    request=Request(base+name,headers={'Range':f'bytes={offset}-{end}'})
                    with urlopen(request,timeout=40) as response:
                        match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                        if response.status!=206 or match is None or int(match[1])!=offset:
                            raise ValueError('官方Range响应不匹配')
                        actual_total=int(match[3]);expected=min(end,actual_total-1)-offset+1
                        if int(match[2])-offset+1!=expected:
                            raise ValueError('官方Range长度不匹配')
                        data=response.read(expected+1)
                        if len(data)!=expected:
                            raise ValueError('分块截断')
                    break
                except Exception:
                    if attempt==3:
                        raise
                    time.sleep(attempt+1)
            with chunk.open('xb') as stream:
                stream.write(data)
            with meta.open('x') as stream:
                json.dump({'total':actual_total},stream)
        if total is not None and actual_total!=total:
            raise ValueError('下载期间总长度变化')
        total=actual_total
        if len(data)!=min(size,total-offset):
            raise ValueError('已有分块长度错误')
        chunks.append(data);offset+=len(data)
    data=b''.join(chunks)
    if hashlib.sha256(data).hexdigest()!=official[name]:
        raise ValueError('完整波形官方SHA256错误：'+name)
    with path.open('xb') as stream:
        stream.write(data)
    print(json.dumps({'downloaded':name,'bytes':len(data),'verified':True}),flush=True)


def fetch(root,stage,protocol=None):
    for db in DATABASES:
        directory=root/db;directory.mkdir(parents=True,exist_ok=True)
        base=f'https://physionet.org/files/{db}/1.0.0/'
        official=checksum_map(retrieve(directory,'SHA256SUMS.txt',base))
        if stage=='metadata':
            records=retrieve(directory,'RECORDS',base,official).decode().split()
            names=[f'{r}.{ext}' for r in records for ext in ('hea','atr')]
            if db=='incartdb':
                names+=['files-patients-diagnoses.txt','record-descriptions.txt']
            names += [n for n in ('LICENSE.txt','LICENSE') if n in official]
        else:
            records=sorted({r['record'] for rows in protocol['splits'].values() for r in rows if r['database']==db})
            names=[f'{r}.dat' for r in records]
            # 官方归档端点，仅用于相同字节的波形；最终仍按固定版本SHA认证。
            base=f'https://archive.physionet.org/physiobank/database/{db}/'
        def one(name):
            if stage=='waveforms':
                retrieve_waveform(directory,name,base,official)
            else:
                retrieve(directory,name,base,official)
        with ThreadPoolExecutor(max_workers=8 if stage=='waveforms' else 4) as pool:
            list(pool.map(one,names))
        print(json.dumps({'database':db,'stage':stage,'verified_files':len(names),'records':len(records)}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--stage',choices=('metadata','waveforms'),required=True)
    parser.add_argument('--protocol',type=Path)
    args=parser.parse_args()
    if args.stage=='waveforms' and not args.protocol:
        parser.error('波形下载必须指定已冻结协议')
    fetch(args.output_dir,args.stage,json.loads(args.protocol.read_text(encoding='utf-8')) if args.protocol else None)
