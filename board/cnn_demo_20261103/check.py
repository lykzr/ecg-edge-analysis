"""离线核对交接镜像、参数和来源；不连接设备，不构建、不写Flash。"""
import hashlib
import json
from pathlib import Path, PureWindowsPath

HERE = Path(__file__).resolve().parent


def check(directory=HERE):
    directory = Path(directory).resolve()
    data = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for name, row in data['files'].items():
        if not name or '\\' in name or PureWindowsPath(name).drive:
            raise ValueError('非法交接路径：' + name)
        path = (directory / name).resolve()
        path.relative_to(directory)
        if not path.is_file():
            raise FileNotFoundError(name)
        if path.stat().st_size != row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('交接文件长度或SHA256不符：' + name)
    for key in ('bit', 'xsa', 'elf', 'init'):
        if data['fp32'][key] not in data['files']:
            raise ValueError('缺少镜像校验：' + key)
    original = json.loads((directory / 'fp32/build_manifest_original.json').read_text(encoding='utf-8'))
    for name, row in data['files'].items():
        if name.startswith('fp32/') and name != 'fp32/build_manifest_original.json':
            if original['files'][row['source']] != {'bytes': row['bytes'], 'sha256': row['sha256']}:
                raise ValueError('原构建清单不匹配：' + name)
    return dict(passed=True, files=len(data['files']), hardware_operated=False,
                scope='交接文件离线完整性；不代表重新构建、INT8精度验收或新板测')


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False))
