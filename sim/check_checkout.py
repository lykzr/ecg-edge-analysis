"""克隆后源码/协议/工程引用完整性检查；只需标准库，不导入训练依赖。"""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def manifest_path(base, name):
    """兼容历史Windows清单；路径仍须是基目录内的相对文件。"""
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError('清单路径必须是非空相对路径')
    portable = PurePosixPath(name.replace('\\', '/'))
    if portable.is_absolute() or PureWindowsPath(name).drive or not portable.parts:
        raise ValueError('清单不接受绝对路径或盘符：'+name)
    base = Path(base).resolve()
    result = base.joinpath(*portable.parts).resolve()
    result.relative_to(base)
    return result


def check(root=ROOT):
    root = Path(root).resolve()
    required = json.loads((root / 'sim/checkout_files.json').read_text(encoding='utf-8'))['required']
    for name in required:
        path = manifest_path(root, name)
        if not path.is_file():
            raise FileNotFoundError('交接缺文件：' + name)
    modules = {Path(n).stem for n in required if n.endswith('.py')}
    parsed = 0
    for name in required:
        if not name.endswith('.py'):
            continue
        tree = ast.parse((root / name).read_text(encoding='utf-8-sig')); parsed += 1
        for node in ast.walk(tree):
            local = []
            if isinstance(node, ast.ImportFrom) and node.module:
                local = [node.module.split('.')[0]]
            elif isinstance(node, ast.Import):
                local = [a.name.split('.')[0] for a in node.names]
            for module in local:
                if module.startswith(('ecg_', 'train_cnn_', 'prepare_cnn_', 'gqrs_')):
                    assert module in modules, (name, module)
    xpr = root / 'vivado/ecg_edge/ecg_edge.xpr'
    project = ET.parse(xpr).getroot()
    assert project.find("./Configuration/Option[@Name='Part']").attrib['Val'] == 'xc7z020clg400-2'
    source_dir = xpr.parent / 'ecg_edge.srcs'
    files = []
    for entry in project.findall('./FileSets/FileSet/File'):
        text = entry.attrib['Path'].replace('$PPRDIR', str(xpr.parent)).replace('$PSRCDIR', str(source_dir))
        assert '$' not in text, text
        path = Path(text.replace('\\', '/')).resolve(); path.relative_to(root)
        assert path.is_file(), str(path)
        files.append(str(path.relative_to(root)))
    assert len(files) == 4, files
    baseline = json.loads((root / 'data/baseline/files.json').read_text(encoding='utf-8'))
    for name, row in baseline['files'].items():
        path = manifest_path(root / 'data/baseline', name)
        assert path.stat().st_size == row['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], name
    return {'passed': True, 'required_files': len(required), 'python_parsed': parsed,
            'xpr_source_files': files, 'baseline_files': len(baseline['files']),
            'scope': 'static checkout completeness, not dependencies installed, training, synthesis or board test'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(check(args.root), ensure_ascii=False))
