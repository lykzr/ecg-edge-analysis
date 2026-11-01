"""只读检查Git交接；可在tmp隔离目录验证跟踪文件，不生成提交副本。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    root = Path(root).resolve()
    inventory = json.loads((root / 'model/handoff_requirements.json').read_text(encoding='utf-8'))
    for name in inventory['git_inputs']:
        path = (root / name).resolve()
        assert path.is_relative_to(root) and path.is_file(), name
    # 核对三个固定模型、完整输入实现和常量；历史provenance中的tmp路径不作运行依赖。
    manifest = json.loads((root / 'model/inference/manifest.json').read_text(encoding='utf-8'))
    for name, spec in manifest['files'].items():
        path = (root / 'model/inference' / name).resolve()
        assert path.is_relative_to(root / 'model/inference'), name
        data = path.read_bytes()
        if spec.get('lf_normalized'):
            data = data.replace(bytes([13, 10]), bytes([10]))
        assert hashlib.sha256(data).hexdigest() == spec['sha256'], name
    return dict(passed=True, git_inputs=len(inventory['git_inputs']),
                model_files=len(manifest['files']),
                external_resources=inventory['external_resources'],
                unavailable_source_materials=inventory['unavailable_source_materials'],
                scope='推理/导出/继续开发输入完整；不代表HGB训练来源已补齐或PL已实现')


def isolated(output):
    output = Path(output).resolve()
    assert output.is_relative_to(ROOT / 'tmp'), '隔离检查只允许输出到项目tmp'
    output.mkdir(parents=True, exist_ok=False)
    repo = output / 'checkout'
    repo.mkdir()
    proc = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True)
    names = [v.decode('utf-8') for v in proc.stdout.split(bytes([0])) if v]
    for name in names:
        source = (ROOT / name).resolve()
        target = (repo / name).resolve()
        assert source.is_relative_to(ROOT) and target.is_relative_to(repo)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    steps = [
        ['sim/check_checkout.py'], ['sim/check_system_release.py'],
        ['sim/check_git_handoff.py'], ['sim/check_hgb_quality.py'],
        ['model/inference/check.py'],
        ['build/export_hgb.py', '--output', 'tmp/parameters'],
    ]
    runs = []
    for i, args in enumerate(steps):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', *args], cwd=repo,
                                capture_output=True, timeout=180)
        (output / ('check_' + str(i) + '.log')).write_bytes(result.stdout + result.stderr)
        runs.append(dict(command=args, returncode=result.returncode, passed=result.returncode == 0))
    summary = dict(passed=all(row['passed'] for row in runs), tracked_files=len(names),
                   steps=runs, python=sys.version,
                   scope='从Git跟踪路径复制当前工作文件作临时验证；无原作者tmp/资料/环境/私有数据，使用本机已有Python依赖；不是远端克隆或空机安装',
                   trained=False, hardware_operated=False)
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--isolated-output', type=Path)
    args = parser.parse_args()
    result = isolated(args.isolated_output) if args.isolated_output else check(args.root)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result['passed'] else 1)
