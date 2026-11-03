"""校验封印后准备可移植加载清单，显式调用才通过JTAG复位运行，不写Flash。"""
import argparse
import json
import sys
from pathlib import Path
from check import check, HERE, ROOT

sys.path.insert(0, str(ROOT / 'board'))
from load_cnn import load


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('xsdb', 'cable', 'port', 'device-id', 'output'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    seal = check()
    data = json.loads((HERE / 'build_manifest_original.json').read_text(encoding='utf-8'))
    # 原始构建收据不改写；仅生成本次克隆路径下的派生加载清单。
    base = HERE.relative_to(ROOT)
    data['files'] = {(base / Path(name).name).as_posix(): row for name, row in data['files'].items()}
    for key in ('bit', 'elf', 'init'):
        data[key] = (base / Path(data[key]).name).as_posix()
    data['sources'] = seal['sources']
    target = Path(args.output).resolve()
    target.relative_to(ROOT / 'tmp')
    target.mkdir(parents=True, exist_ok=False)
    manifest = target / 'load_manifest.json'
    manifest.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    load(manifest, args.xsdb, args.cable, args.port, args.device_id, target / 'jtag')
