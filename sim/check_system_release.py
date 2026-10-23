"""离线核对精简发布：只验证 JTAG 烧录产物，证据/源码在仓库中核对。"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from check_board_evidence import check as check_board_evidence

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(base, name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('发布路径必须为正斜杠相对路径：' + str(name))
    p = PurePosixPath(name)
    if p.is_absolute() or PureWindowsPath(name).drive or '..' in p.parts:
        raise ValueError('发布路径越界：' + name)
    target = base.joinpath(*p.parts).resolve()
    target.relative_to(base.resolve())
    return target


def check_files(directory, manifest):
    for name, row in manifest['files'].items():
        path = safe(directory, name)
        assert path.is_file(), '缺文件：' + name
        assert path.stat().st_size == row['bytes'], '字节不符：' + name
        assert digest(path) == row['sha256'], 'SHA256 不符：' + name
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    assert actual == set(manifest['files']) | {'manifest.json'}, '存在未列明文件或缺少清单'


def check_subset(directory, sub):
    base = directory / sub
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
    check_files(base, manifest)
    hardware = base / 'hardware'
    with zipfile.ZipFile(hardware / 'ecg_system_candidate.xsa') as z:
        assert z.read('ecg_system_candidate.bit') == (hardware / 'ecg_system_candidate.bit').read_bytes()
    elf = base / 'prebuilt' / ('ecg_smoke.elf' if sub == 'smoke' else 'ecg_bridge.elf')
    blob = elf.read_bytes()
    assert blob[:4] == b'\x7fELF' and blob[4] == 1 and blob[5] == 1
    assert int.from_bytes(blob[18:20], 'little') == 40
    return manifest


def check(directory, repository):
    directory = Path(directory).resolve()
    repository = Path(repository).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['version'] == '20261021-system-jtag-v1'
    assert manifest['flash_programming'] == 'NOT_PERFORMED'
    check_files(directory, manifest)

    artifacts = json.loads((directory / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifacts['version'] == manifest['version']
    assert not any(artifacts['scope'][k] for k in ('wireless', 'manual_gui', 'ecg_accuracy', 'cnn_int8_pl', 'flash'))
    assert artifacts['scope']['smoke'] == 'USER_REPORTED_PASS'
    assert artifacts['scope']['bridge'] == 'FINITE_DIGITAL_BOARD_PASS'

    smoke = check_subset(directory, 'smoke')
    bridge = check_subset(directory, 'bridge')
    assert smoke['board_execution'] == 'USER_REPORTED_PASS'
    assert smoke['flash_programming'] == 'NOT_PERFORMED'
    assert bridge['flash_programming'] == 'NOT_PERFORMED'
    smoke_bit = digest(directory / 'smoke/hardware/ecg_system_candidate.bit')
    bridge_bit = digest(directory / 'bridge/hardware/ecg_system_candidate.bit')
    assert smoke_bit != bridge_bit
    assert bridge['elf_sha256'] == artifacts['bridge_build']['elf_sha256'] == digest(directory / 'bridge/prebuilt/ecg_bridge.elf')
    assert artifacts['bridge_build']['xsa_sha256'] == digest(directory / 'bridge/hardware/ecg_system_candidate.xsa')
    assert artifacts['bridge_build']['bit_sha256'] == bridge_bit
    assert artifacts['bridge_build']['psinit_sha256'] == digest(directory / 'bridge/hardware/ps7_init.tcl')
    for name, h in artifacts['smoke_core_unchanged'].items():
        assert digest(directory / 'smoke' / name) == h, name

    for name, row in artifacts['sources'].items():
        path = safe(directory, name)
        assert path.stat().st_size == row['bytes']
        assert digest(path) == row['sha256'], name
        source = safe(repository, row['source'])
        assert source.is_file(), '仓库来源缺失：' + row['source']
        assert digest(source) == row['sha256'], '仓库来源哈希不符：' + row['source']

    for name, expected in artifacts['evidence'].items():
        path = safe(repository, name)
        assert path.is_file(), '证据缺失：' + name
        assert digest(path) == expected, '证据哈希不符：' + name

    for sub in ('smoke', 'bridge'):
        for name, expected in json.loads((directory / sub / 'manifest.json').read_text(encoding='utf-8')).get('source_sha256', {}).items():
            assert digest(repository / name) == expected, name

    assert not any((directory / p).exists() for p in ('BOOT.BIN', 'boot.bif', 'fsbl.elf', 'hello_world.elf'))
    cases = check_board_evidence(repository)
    return {
        'passed': True,
        'version': manifest['version'],
        'files': len(manifest['files']) + 1,
        'smoke_files': len(smoke['files']),
        'bridge_files': len(bridge['files']),
        'evidence_checked': len(artifacts['evidence']),
        'sources_checked': len(artifacts['sources']),
        'cases': cases,
        'hardware_operated': False,
        'scope': 'offline slim release check; evidence/sources verified in repository; no board operation',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'releases/latest')
    parser.add_argument('--repository', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(check(args.directory, args.repository), ensure_ascii=False))
