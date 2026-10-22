"""生成DS隔离副本；正式交接保留此生成器，派生副本放tmp。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def prepare(root, output, raw=None):
    root, output = root.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError('目标已存在，禁止覆盖：'+str(output))
    if output == root or root.is_relative_to(output):
        raise ValueError('目标不能是项目或其父目录')
    if output.is_relative_to(root) and not output.is_relative_to(root/'tmp'):
        raise ValueError('项目内隔离副本必须放tmp')
    p = json.loads((root/'data/qrs_research_protocol.json').read_text(encoding='utf-8'))
    files = set(p['frozen_sha256']) | {
        'data/qrs_research_protocol.json', 'data/qrs_v5_protocol.json',
        'data/qrs_v4_protocol.json', 'data/download_mitdb_records.py',
        'docs/ds_task.md', 'docs/qrs_research.md', 'report/project_plan.md',
        'LICENSE', 'third_party.md', 'AGENTS.md',
    }
    for name, sha in p['frozen_sha256'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != sha:
            raise ValueError('冻结输入变化：'+name)
    output.mkdir(parents=True)
    for folder in ['input/project', 'input/raw', 'work', 'output', 'logs']:
        (output/folder).mkdir(parents=True, exist_ok=True)
    for name in sorted(files):
        target = output/'input/project'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root/name, target)
    if raw is not None:
        official_path = raw/'SHA256SUMS.txt'
        official = {line.split()[1].lstrip('*'): line.split()[0]
                    for line in official_path.read_text().splitlines()}
        shutil.copy2(official_path, output/'input/raw/SHA256SUMS.txt')
        for rec in ['118', '119']:
            for suffix in ['hea', 'dat', 'atr']:
                source = raw/f'{rec}.{suffix}'
                if not source.is_file():
                    raise FileNotFoundError('原始数据缺文件：'+str(source))
                if hashlib.sha256(source.read_bytes()).hexdigest() != official.get(source.name):
                    raise ValueError('原始数据官方SHA不符：'+source.name)
                shutil.copy2(source, output/'input/raw'/source.name)
    inputs = {}
    for f in sorted((output/'input').rglob('*')):
        if f.is_file():
            inputs[f.relative_to(output).as_posix()] = {
                'bytes': f.stat().st_size, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest(),
            }
    (output/'input_manifest.json').write_text(json.dumps(inputs, indent=2)+'\n', encoding='utf-8')
    shutil.copy2(root/'docs/ds_task.md', output/'TASK.md')
    (output/'AGENTS.md').write_text(
        '# DS隔离执行约束\n\n先读TASK.md。只可写work/、output/、logs/。'
        'input/、input_manifest.json、check_inputs.py、TASK.md和本文件只读。'
        '运行前后执行python -B check_inputs.py；失败立即停止，不恢复或重算清单。'
        '禁止访问/修改原工程，禁止Git、安装、下载、训练、板卡、Computer Use。'
        '读取input/project/AGENTS.md；用户本轮隔离要求优先，日志只写此副本。'
        '缺依赖仅报告，不安装。完成TASK后最后写output/DONE.json并停止。\n', encoding='utf-8')
    (output/'check_inputs.py').write_text(
        '"""核对输入未变化；只读检查，不自动修复。"""\n'
        'import hashlib,json\nfrom pathlib import Path\n'
        'r=Path(__file__).resolve().parent\n'
        'm=json.loads((r/"input_manifest.json").read_text())\n'
        'actual={p.relative_to(r).as_posix() for p in (r/"input").rglob("*") if p.is_file()}\n'
        'assert actual==set(m), "输入文件集合发生变化"\n'
        'for n,v in m.items():\n'
        ' p=r/n\n'
        ' assert p.stat().st_size==v["bytes"] and hashlib.sha256(p.read_bytes()).hexdigest()==v["sha256"],n\n'
        'print(json.dumps({"passed":True,"input_files":len(m)}))\n', encoding='utf-8')
    return {'passed': True, 'output': str(output), 'input_files': len(inputs),
            'includes_raw_118_119': raw is not None,
            'scope': 'isolated input copy and change detection, not OS permission isolation or DS execution'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--raw-dir', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.output_dir, args.raw_dir), ensure_ascii=False))
