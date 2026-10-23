"""显式获取或只读核验官方NST压力数据；不安装依赖、不改已有文件。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
NST='https://physionet.org/files/nstdb/1.0.0/'
MIT='https://physionet.org/files/mitdb/1.0.0/'


def checksum(blob):
    return hashlib.sha256(blob).hexdigest()


def fetch(directory, verify_only=False):
    directory=Path(directory).resolve();directory.relative_to(ROOT/'tmp')
    if verify_only and not directory.is_dir():raise FileNotFoundError(directory)
    if not verify_only:directory.mkdir(parents=True,exist_ok=True)
    def read(name,url):
        path=directory/name
        if path.exists():return path.read_bytes()
        if verify_only:raise FileNotFoundError(path)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url,timeout=60) as response:
                    blob=response.read()
                break
            except OSError:
                if attempt==2:raise
        with path.open('xb') as stream:stream.write(blob)
        return blob
    plans=[]
    for base,names,sum_name in [
        (NST,[b+s for b in ('118','119') for s in ('e24','e18','e12','e06','e00','e_6')],'SHA256SUMS.txt'),
        (MIT,['118','119'],'MITDB_SHA256SUMS.txt')]:
        blob=read(sum_name,base+'SHA256SUMS.txt')
        official={f[1].lstrip('*'):f[0] for line in blob.decode().splitlines() if len(f:=line.split())==2}
        for record in names:
            for ext in ('hea','dat','atr'):
                name=record+'.'+ext
                plans.append((name,base+name,official[name]))
    def verified(plan):
        name,url,sha=plan;blob=read(name,url)
        if checksum(blob)!=sha:raise ValueError('官方SHA不符，保留文件并停止：'+name)
        return dict(name=name,url=url,sha256=sha,bytes=len(blob))
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(verified,plans))
    index=directory/'verified_checksums.json'
    if index.exists():
        old=json.loads(index.read_text())
        if {r['name']:r['sha256'] for r in old}!={r['name']:r['sha256'] for r in rows}:
            raise ValueError('现存派生索引与官方数据不符，不覆盖')
    elif verify_only:
        raise FileNotFoundError(index)
    else:
        with index.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(rows,indent=2)+'\n')
    return dict(passed=True,files=len(rows),verify_only=verify_only,
                raw_dir=str(directory),scope='official checksum verification, not QRS scoring')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-dir',type=Path,required=True)
    p.add_argument('--verify-only',action='store_true',help='只读核对本地数据；不联网、不写入')
    a=p.parse_args();print(json.dumps(fetch(a.raw_dir,a.verify_only),ensure_ascii=False))
