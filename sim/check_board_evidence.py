"""核验原有有限数字实板证据；只读仓库记录，不重跑或冒称新上板。"""
import binascii
import hashlib
import json
from pathlib import Path


def evidence(base, case, count=None, reason=None):
    folder = base / case
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    if not summary['passed']:
        raise ValueError('原实板用例未通过')
    raw = (folder / 'usb_rx.log').read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('接收尾行不完整')
    controls, wave, events = [], [], []
    end = False
    for line in raw.splitlines():
        f = line.decode('ascii').split(',')
        if f[0] == 'A':
            body, crc = line.rsplit(b'*', 1)
            if binascii.crc32(body) != int(crc, 16):
                raise ValueError('确认CRC错误')
            controls.append(body.decode('ascii').split(','))
        elif f[0] == 'W':
            seq, n = int(f[1]), int(f[2])
            if seq != len(wave) or len(f) != 3 + 2*n:
                raise ValueError('波形序号/长度异常')
            for i in range(n):
                if f[4+2*i] != 'NA':
                    raise ValueError('未提供的滤波被填值')
                wave.append(int(f[3+2*i]))
        elif f[0] == 'E':
            events.append(f)
        elif f[0] == 'T':
            if f[4] != 'NA' or f[6:9] != ['0', '-1', '0']:
                raise ValueError('状态报告异常/已知丢弃')
        elif line.startswith(b'L,I,END reason=completed '):
            end = True
        elif f[0] not in ('H', 'L'):
            raise ValueError('未知接收报文')
    if reason:
        assert not wave and not events and controls[-1][3:] == ['0', 'ERROR', reason]
    else:
        assert count == len(wave) == summary['confirmed'] == summary['echoed'] and end
        assert controls[-1][3:] == [str(count), 'DONE', 'NA']
        assert all(v == ((20000 if i//500 % 2 == 0 else -20000) if i % 500 == 100 else 0)
                   for i, v in enumerate(wave))
        assert len(events) == count//500
        for i, f in enumerate(events):
            assert list(map(int, f[1:4])) == [i+1, 70+500*i, 0 if i == 0 else 500]
            assert f[5:] == ['?', '-1']
    return dict(samples=len(wave), events=len(events), reason=reason)


def check(repository):
    base = Path(repository) / 'docs/records/system_board_20261020'
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
    for name, row in manifest['files'].items():
        path = (base / name).resolve()
        path.relative_to(base.resolve())
        data = path.read_bytes()
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], name
    cases = dict(paced=evidence(base, 'paced_01', 60003), recovery=evidence(base, 'paced_03', 5003))
    for case, reason in [('bad-crc_02', 'BAD_CRC'), ('partial_03', 'PARTIAL_TIMEOUT'), ('idle_03', 'INPUT_TIMEOUT')]:
        cases[case] = evidence(base, case, reason=reason)
    return cases
