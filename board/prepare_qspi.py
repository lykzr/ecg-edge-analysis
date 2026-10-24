"""从匹配构建或发布重建QSPI镜像；只打包，不连接板卡或写Flash。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

from runtime_artifacts import resolve_runtime_artifacts

ROOT = Path(__file__).resolve().parents[1]


def row(path):
    return dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def checked(folder, name, expected):
    path = (folder / name).resolve()
    path.relative_to(folder.resolve())
    if row(path) != expected:
        raise ValueError('输入文件与清单不符：' + name)
    return path


def run(output, bootgen, release, build_manifest=None):
    output = Path(output).resolve()
    output.relative_to(ROOT / 'tmp')
    if output.exists():
        raise FileExistsError('不覆盖已有输出：' + str(output))
    bootgen = Path(bootgen).resolve()
    if not bootgen.is_file():
        raise FileNotFoundError(bootgen)
    release = Path(release).resolve()
    runtime = release / 'runtime500'
    meta = json.loads((runtime / 'manifest.json').read_text(encoding='utf-8'))
    bit = checked(runtime, 'hardware/ecg_system_candidate.bit', meta['files']['hardware/ecg_system_candidate.bit'])
    app = checked(runtime, 'prebuilt/ecg_runtime500.elf', meta['files']['prebuilt/ecg_runtime500.elf'])
    if build_manifest:
        build, paths = resolve_runtime_artifacts(build_manifest, expected_rate=500)
        if build['build_id'] != meta['build_id'] or row(paths['elf']) != row(app) or row(paths['bit']) != row(bit):
            raise ValueError('构建与当前运行时发布不是同一组合')
        found = [ROOT / n for n in build['files'] if n.endswith('/fsbl.elf')]
        if len(found) != 1:
            raise ValueError('构建清单须唯一指定FSBL')
        fsbl = found[0]
    else:
        qspi = release / 'qspi'
        bootmeta = json.loads((qspi / 'manifest.json').read_text(encoding='utf-8'))
        if bootmeta['build_id'] != meta['build_id']:
            raise ValueError('发布FSBL与应用构建身份不匹配')
        fsbl = checked(qspi, 'fsbl.elf', bootmeta['files']['fsbl.elf'])
    output.mkdir(parents=True)
    for source, name in [(fsbl, 'fsbl.elf'), (bit, 'ecg_system_candidate.bit'), (app, 'ecg_runtime500.elf')]:
        shutil.copyfile(source, output / name)
    (output / 'boot.bif').write_text('the_ROM_image:\n{\n  [bootloader] fsbl.elf\n  ecg_system_candidate.bit\n  ecg_runtime500.elf\n}\n', encoding='ascii')

    def invoke(args, log):
        command = [str(bootgen)] + args
        if os.name == 'nt':
            script = '& ' + ' '.join("'" + v.replace("'", "''") + "'" for v in command) + '; exit $LASTEXITCODE'
            command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script]
        with (output / log).open('xb') as stream:
            result = subprocess.run(command, cwd=output, stdout=stream, stderr=subprocess.STDOUT, timeout=90)
        if result.returncode:
            raise RuntimeError('Bootgen失败，保留日志：' + log)

    invoke(['-arch', 'zynq', '-image', 'boot.bif', '-o', 'BOOT.BIN'], 'bootgen.log')
    invoke(['-arch', 'zynq', '-read', 'BOOT.BIN'], 'boot_read.log')
    blob = (output / 'BOOT.BIN').read_bytes()
    if struct.unpack_from('<II', blob, 0x20) != (0xAA995566, 0x584C4E58) or len(blob) > 32 * 1024 * 1024:
        raise ValueError('镜像不是规定容量内的Zynq启动格式')
    info = dict(build_id=meta['build_id'], flash_type='qspi-x4-single', offset=0,
                files={name: row(output / name) for name in ('BOOT.BIN', 'fsbl.elf', 'ecg_system_candidate.bit', 'ecg_runtime500.elf', 'boot.bif')},
                flash_written=False, scope='matched image packaging only; not programming or boot acceptance')
    (output / 'image_manifest.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(info))
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--bootgen', required=True)
    parser.add_argument('--release', default=str(ROOT / 'releases/latest'))
    parser.add_argument('--manifest', help='首次打包时指定同源构建清单，后续可仅从完整发布重建')
    args = parser.parse_args()
    run(args.output, args.bootgen, args.release, args.manifest)
