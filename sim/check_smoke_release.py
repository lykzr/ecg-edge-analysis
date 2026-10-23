"""离线核验精简 smoke 发布：硬件/ELF/脚本与仓库源码、证据一致；不连接板卡。"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(directory, repository):
    directory = directory.resolve()
    repository = repository.resolve()
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['version'] == '20261017-ecg-smoke-jtag-v1'
    assert manifest['board_execution'] == 'USER_REPORTED_PASS'
    assert manifest['flash_programming'] == 'NOT_PERFORMED'
    for name, row in manifest['files'].items():
        rel = PurePosixPath(name)
        assert not rel.is_absolute() and '..' not in rel.parts
        path = directory.joinpath(*rel.parts).resolve()
        path.relative_to(directory)
        assert path.is_file(), '缺文件：' + name
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], name
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    assert actual == set(manifest['files']) | {'manifest.json'}, '存在未列明文件或缺少清单'

    hardware = directory / 'hardware'
    with zipfile.ZipFile(hardware / 'ecg_system_candidate.xsa') as xsa:
        assert xsa.read('ecg_system_candidate.bit') == (hardware / 'ecg_system_candidate.bit').read_bytes()
    elf = (directory / 'prebuilt/ecg_smoke.elf').read_bytes()
    assert elf[:4] == b'\x7fELF' and elf[4] == 1 and elf[5] == 1
    assert int.from_bytes(elf[18:20], 'little') == 40

    for name, expected in manifest.get('source_sha256', {}).items():
        source = repository / name
        assert source.is_file(), '仓库源码缺失：' + name
        assert digest(source) == expected, '仓库源码哈希不符：' + name

    evidence = ['docs/records/smoke_board_20261017/uart_smoke_pass.log']
    for name in evidence:
        path = repository / name
        assert path.is_file(), '证据缺失：' + name

    assert not any((directory / p).exists() for p in ('BOOT.BIN', 'boot.bif', 'fsbl.elf', 'hello_world.elf'))
    return {
        'passed': True,
        'version': manifest['version'],
        'payload_files': len(manifest['files']),
        'matched_repository_source': True,
        'board_evidence_in_repository': True,
        'hardware_operated_by_checker': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'releases/latest/smoke')
    parser.add_argument('--repository', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(check(args.directory, args.repository), ensure_ascii=False))
