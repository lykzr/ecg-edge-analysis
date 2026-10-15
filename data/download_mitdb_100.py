"""按需获取官方100号记录；已有文件仅核对，不覆盖，原始数据留在tmp。"""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

EXPECTED = {
    '100.hea':'60ebc904c7bf3e04d142638d3fd5c903e8dc9f10f1ea3264e07926aa089ee75e',
    '100.dat':'b2ea3c250e56e48f4b7b90697832b8ecd1afa1e0bb31f2dcfea4ed6e1075a639',
    '100.atr':'8d8a5349fb16638ebbf649f1779d12e96d91b736b2aafe59db43719ae583d471',
}
BASE='https://physionet.org/files/mitdb/1.0.0/'


def fetch(output):
    output.mkdir(parents=True,exist_ok=True)
    for name in ['SHA256SUMS.txt',*EXPECTED]:
        destination=output/name
        if not destination.exists():
            with urlopen(BASE+name,timeout=60) as response:
                data=response.read()
            if name in EXPECTED and hashlib.sha256(data).hexdigest()!=EXPECTED[name]:
                raise ValueError(f'官方文件与固定版本哈希不符：{name}')
            with destination.open('xb') as stream:
                stream.write(data)
    official={line.split()[1].lstrip('*'):line.split()[0]
              for line in (output/'SHA256SUMS.txt').read_text().splitlines()}
    for name,digest in EXPECTED.items():
        if official.get(name)!=digest or hashlib.sha256((output/name).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'校验失败：{name}；停止，不覆盖现有文件')
    print('PASS MITDB_100_HASHES',output.resolve())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,
                        default=Path(__file__).resolve().parents[1]/'tmp/mitdb_100/raw')
    args=parser.parse_args()
    fetch(args.output_dir)
