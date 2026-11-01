"""隔离进程调用冻结完整模型；仅接收整段连续500Hz心电，不训练。"""
from pathlib import Path
import hashlib
import json
import sys

PROJECT = Path(__file__).resolve().parents[4]
MODULE = PROJECT / 'model/inference'


def run(payload):
    profile = json.loads((MODULE / 'integration_profile.json').read_text(encoding='utf-8'))
    if profile['fold'] != 0 or profile['model_version'] != 'v92':
        raise ValueError('联调模型配置已变化，需重新验收')
    manifest = json.loads((MODULE / 'manifest.json').read_text(encoding='utf-8'))
    for name, spec in manifest['files'].items():
        path = (MODULE / name).resolve()
        if not path.is_relative_to(MODULE):
            raise ValueError('模型清单路径不合法')
        body = path.read_bytes()
        if spec['lf_normalized']:
            body = body.replace(b'\r\n', b'\n')
        if hashlib.sha256(body).hexdigest() != spec['sha256']:
            raise ValueError('模型完整性检查失败')
    for name, expected in [(profile['model_file'], profile['model_sha256']),
                           ('config.json', profile['config_sha256'])]:
        # 配置锁的是原字节；Git checkout可能转换文本换行。
        body = (MODULE / name).read_bytes()
        candidates = [body, body.replace(b'\r\n', b'\n'), body.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')]
        if not any(hashlib.sha256(value).hexdigest() == expected for value in candidates):
            raise ValueError('冻结权重或配置身份不符')
    sys.path.insert(0, str(MODULE))
    from adapter import analyze_ecg
    result = analyze_ecg(payload['samples'], fold=0, preprocess=payload['preprocess'], sampling_hz=500)
    result['model_sha256'] = profile['model_sha256']
    return result


if __name__ == '__main__':
    try:
        body = sys.stdin.buffer.read(8_000_001)
        if len(body) > 8_000_000:
            raise ValueError('模型输入过大')
        result = run(json.loads(body))
        sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception:
        # 不把主机路径、子进程输出或内部异常回传给网页。
        sys.stderr.write('HGB推理或完整性检查失败；请先运行模型check.py核对环境和资产。')
        sys.exit(2)
