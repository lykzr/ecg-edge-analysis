"""按冻结协议获取少量MIT-BIH记录；校验官方SHA256，保留已有文件。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://physionet.org/files/mitdb/1.0.0/'


def fetch(output, protocol):
    output.mkdir(parents=True,exist_ok=True)
    checksum = output/'SHA256SUMS.txt'
    if not checksum.exists():
        with urlopen(BASE+'SHA256SUMS.txt',timeout=60) as response:
            payload = response.read()
        with checksum.open('xb') as stream:
            stream.write(payload)
    official = {line.split()[1].lstrip('*'):line.split()[0]
                for line in checksum.read_text().splitlines()}
    records = protocol['development_records'] + protocol['evaluation_records']
    def fetch_record(record):
        for extension in ('hea','dat','atr'):
            name = f'{record}.{extension}'
            path = output/name
            if path.exists():
                payload = path.read_bytes()
            else:
                with urlopen(BASE+name,timeout=60) as response:
                    payload = response.read()
                if hashlib.sha256(payload).hexdigest() != official[name]:
                    raise ValueError(f'下载校验失败：{name}')
                with path.open('xb') as stream:
                    stream.write(payload)
            if hashlib.sha256(payload).hexdigest() != official[name]:
                raise ValueError(f'已有文件校验失败：{name}，停止且不覆盖')
        print('PASS HASHES',record,flush=True)
    # 少量并行请求，避免逐条下载受慢连接累积拖延；每个文件只有一个写入任务。
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch_record,records))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--protocol',type=Path,default=ROOT/'data/qrs_v4_protocol.json')
    args = parser.parse_args()
    fetch(args.output_dir,json.loads(args.protocol.read_text(encoding='utf-8')))
