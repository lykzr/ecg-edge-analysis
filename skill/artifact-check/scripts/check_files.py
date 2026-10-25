"""按外部提供的字节/SHA清单只读核对文件；不创建或信任未知来源清单。"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys


def check(root, manifest):
    root=Path(root).resolve()
    rows=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))['files']
    if not isinstance(rows,dict) or not rows:
        raise ValueError('files必须是非空映射')
    total=0
    for name, row in rows.items():
        if not isinstance(name,str) or not name or '\\' in name or '\x00' in name:
            raise ValueError('非法相对路径')
        relative=PurePosixPath(name)
        if relative.is_absolute() or PureWindowsPath(name).drive or '..' in relative.parts or not relative.parts:
            raise ValueError('路径越界：'+name)
        path=(root/relative).resolve();path.relative_to(root)
        size=row['bytes'];expected=row['sha256']
        if type(size) is not int or size<0 or not isinstance(expected,str) or not re.fullmatch('[0-9a-fA-F]{64}',expected):
            raise ValueError('非法字节数或SHA256：'+name)
        if not path.is_file() or path.stat().st_size!=size:
            raise ValueError('文件缺失或字节数不同：'+name)
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        if digest.hexdigest()!=expected.lower():
            raise ValueError('SHA256不同：'+name)
        total+=size
    return dict(passed=True,files=len(rows),bytes=total,scope='listed file integrity only; not source authenticity or hardware compatibility')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True);p.add_argument('--manifest',required=True)
    args=p.parse_args()
    try:result=check(args.root,args.manifest)
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps(dict(passed=False,error=str(error)),ensure_ascii=False));sys.exit(1)
    print(json.dumps(result,ensure_ascii=False))
