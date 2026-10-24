"""从实际构建清单提取唯一匹配文件；不连接设备、不猜测旧发布路径。"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def resolve_runtime_artifacts(manifest, *, expected_rate=360, root=ROOT):
    root = Path(root).resolve()
    data = json.loads(Path(manifest).read_text(encoding='utf-8'))
    # 早期360Hz清单无sampling_hz；不允许据此接受新版500Hz清单。
    if data.get('sampling_hz', 360) != expected_rate:
        raise ValueError('验收脚本采样率与构建清单不符')
    paths = {}
    for name, row in data['files'].items():
        path = (root / name).resolve()
        path.relative_to(root)
        if path.stat().st_size != row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('匹配文件不符：' + name)
        paths[name] = path
    for name, value in data['sources'].items():
        path = (root / name).resolve()
        path.relative_to(root)
        if hashlib.sha256(path.read_bytes()).hexdigest() != value:
            raise ValueError('当前源与ELF不符：' + name)
    selected = {}
    for role, basename in [('bit', 'ecg_system_candidate.bit'), ('xsa', 'ecg_system_candidate.xsa'), ('init', 'ps7_init.tcl')]:
        found = [p for p in paths.values() if p.name == basename]
        if len(found) != 1:
            raise ValueError('清单必须唯一指定：' + basename)
        selected[role] = found[0]
    if data['elf'] not in paths or paths[data['elf']].suffix != '.elf':
        raise ValueError('ELF未列入校验清单')
    selected['elf'] = paths[data['elf']]
    return data, selected
