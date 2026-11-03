"""离线校验三核匹配镜像与源码；不访问板卡。"""
import hashlib
import json
from pathlib import Path, PureWindowsPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def check():
    data = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    for name, row in data['files'].items():
        if not name or '\\' in name or PureWindowsPath(name).drive:
            raise ValueError('非法镜像路径：' + name)
        path = (HERE / name).resolve()
        path.relative_to(HERE)
        if path.stat().st_size != row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('镜像校验失败：' + name)
    for name, digest in data['sources'].items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('构建源码已变化，请重建匹配镜像：' + name)
    return data


if __name__ == '__main__':
    data = check()
    print(json.dumps(dict(passed=True, files=len(data['files']), sources=len(data['sources']), hardware_operated=False)))
