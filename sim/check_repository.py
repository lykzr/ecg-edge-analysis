"""检查实际Git跟踪边界、必要文件和文档链接；不复制工程或操作设备。"""
import argparse
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PREFIXES = ('tmp/', 'docs/archive/', 'docs/reference/', 'docs/records/', 'releases/history/')
LOCAL_FILES = {'myself.md', 'board/package_submission.py', 'board/package_system.py', 'sim/submission_files.json'}

def git(root, *args, data=None):
    result = subprocess.run(['git', '-C', str(root), *args], input=data, capture_output=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout

def inspect(root, tracked, required, ignored):
    root = Path(root).resolve()
    tracked = set(tracked)
    errors = []
    for name in sorted(tracked):
        if name in LOCAL_FILES or name.startswith(LOCAL_PREFIXES):
            errors.append('不应跟踪本地资料：' + name)
        if not (root / name).is_file():
            errors.append('跟踪文件缺失：' + name)
    errors.extend('已跟踪但被忽略：' + n for n in sorted(ignored))
    errors.extend('必需文件未跟踪：' + n for n in sorted(set(required) - tracked))
    links = 0
    for name in sorted(tracked):
        path = root / name
        if path.suffix != '.md' or not path.is_file():
            continue
        # 检查Markdown内联链接/图片；标题锚点和外部URL不作为文件路径。
        for part in path.read_text(encoding='utf-8-sig').split('](')[1:]:
            raw = part.split(')', 1)[0].strip()
            if raw.startswith('<') and '>' in raw:
                raw = raw[1:raw.index('>')]
            else:
                raw = raw.split(' ', 1)[0]
            dest = unquote(raw.split('#', 1)[0])
            if not dest or ':' in dest or dest.startswith('//'):
                continue
            links += 1
            target = (path.parent / dest).resolve()
            if not target.is_relative_to(root):
                errors.append('链接越出仓库：' + name + ' → ' + dest)
                continue
            rel = target.relative_to(root).as_posix()
            if not target.exists():
                errors.append('链接目标缺失：' + name + ' → ' + dest)
            elif target.is_file() and rel not in tracked:
                errors.append('链接目标未跟踪：' + name + ' → ' + dest)
            elif target.is_dir() and not any(n.startswith(rel + '/') for n in tracked):
                errors.append('链接目录没有跟踪内容：' + name + ' → ' + dest)
    return dict(passed=not errors, tracked_files=len(tracked), required_files=len(required), links_checked=links, errors=errors, scope='实际Git索引与本地文件；不检查远端、不代表构建或实板验收')

def check(root=ROOT):
    root = Path(root).resolve()
    tracked = [n.decode('utf-8') for n in git(root, 'ls-files', '-z').split(bytes([0])) if n]
    data = bytes([0]).join(n.encode('utf-8') for n in tracked) + bytes([0])
    ignored = [n.decode('utf-8') for n in git(root, 'check-ignore', '--no-index', '-z', '--stdin', data=data).split(bytes([0])) if n]
    required = json.loads((root / 'sim/checkout_files.json').read_text(encoding='utf-8'))['required']
    return inspect(root, tracked, required, ignored)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = check(args.root)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
