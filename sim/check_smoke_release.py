"""离线核验smoke release的文件、证据、源码同步和匹配硬件；不连接板卡。"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(directory):
    directory = directory.resolve()
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    artifacts = json.loads((directory / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifacts['version'] == '20261017-ecg-smoke-jtag-v1'
    assert manifest['board_execution'] == 'USER_REPORTED_PASS'
    assert manifest['flash_programming'] == 'NOT_PERFORMED'
    for name, row in manifest['files'].items():
        rel = PurePosixPath(name)
        assert not rel.is_absolute() and '..' not in rel.parts
        path = directory.joinpath(*rel.parts).resolve(); path.relative_to(directory)
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], name
    assert {row['path'] for row in artifacts['files']} == set(manifest['files']) | {'manifest.json'}
    for row in artifacts['files']:
        path = directory / row['path']
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], row['path']
    historical_tooling_drift = []
    portable_tooling = {'board/build_ecg_smoke.py', 'board/package_ecg_smoke.py', 'sim/check_smoke_release.py'}
    for row in artifacts['sourceFiles'] + artifacts['documentationFiles']:
        path = ROOT / row['path']
        if digest(path) != row['sha256'] and row['path'] in portable_tooling:
            # 归档清单记录当时工具；只允许列明的非算法工具发生迁移，逐项披露。
            historical_tooling_drift.append(row['path'])
        else:
            assert digest(path) == row['sha256'], row['path']
    for name, expected in artifacts['validatedCoreFiles'].items():
        assert digest(directory / name) == expected, name
    with zipfile.ZipFile(directory / 'hardware/ecg_system_candidate.xsa') as xsa:
        assert xsa.read('ecg_system_candidate.bit') == (directory / 'hardware/ecg_system_candidate.bit').read_bytes()
    elf = (directory / 'prebuilt/ecg_smoke.elf').read_bytes()
    assert elf[:4] == b'\x7fELF' and elf[4] == 1 and elf[5] == 1 and int.from_bytes(elf[18:20], 'little') == 40
    assert not any((directory / p).exists() for p in ('BOOT.BIN', 'boot.bif', 'fsbl.elf', 'hello_world.elf'))
    launch = json.loads((directory / 'board/launch_template.json').read_text(encoding='utf-8'))['configurations'][0]['targetSetup']
    assert launch['resetSystem'] and launch['programDevice']
    assert launch['zynqInitialization']['usingPs7Init']['runPs7Init']
    assert launch['zynqInitialization']['usingPs7Init']['runPs7PostInit']
    assert len(launch['downloadElf']) == 1 and not launch['downloadElf'][0]['stopAtEntry']
    uart = (ROOT / 'docs/records/smoke_board_20261017/uart_smoke_pass.log').read_text(encoding='utf-8-sig')
    expected = [s.strip() for s in (directory / 'expected_uart.txt').read_text().splitlines() if s.strip()]
    lines = [s.strip() for s in uart.splitlines() if s.strip() and s.strip() != 'Synthetic samples; no ADC; no clinical accuracy claim.']
    assert lines == expected and not any(s.startswith('FAIL') for s in lines)
    for name, source in [('src/ps/ecg_smoke/main.c', 'src/ps/ecg_smoke/main.c'),
                         ('board/capture_uart.ps1', 'board/smoke_handoff/capture_uart.ps1'),
                         ('board/run_smoke.ps1', 'board/smoke_handoff/run_smoke.ps1'),
                         ('board/run_smoke.tcl', 'board/smoke_handoff/run_smoke.tcl')]:
        assert digest(directory / name) == digest(ROOT / source), name
    return {'passed': True, 'version': artifacts['version'], 'payload_files': len(manifest['files']),
            'matched_board_evidence': True, 'new_capture_helper_hardware_retested': False,
            'hardware_operated_by_checker': False,
            'historical_tooling_changed': historical_tooling_drift}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'releases/latest/smoke')
    args = parser.parse_args()
    print(json.dumps(check(args.directory), ensure_ascii=False))
