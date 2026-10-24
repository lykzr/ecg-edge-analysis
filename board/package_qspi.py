"""把已验证QSPI镜像加入本地交付候选；不写Flash、不自动归档或替换latest。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
VERSION = '20261025-runtime500-qspi-v1'


def row(path):
    return dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def seal(folder, **fields):
    files = {p.relative_to(folder).as_posix(): row(p) for p in sorted(folder.rglob('*')) if p.is_file() and p != folder/'manifest.json'}
    (folder/'manifest.json').write_text(json.dumps(dict(schema=1, version=VERSION, **fields, files=files), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def package(image_dir, receipt_path, output):
    image_dir = Path(image_dir).resolve()
    receipt_path = Path(receipt_path).resolve()
    receipt_path.relative_to(ROOT)
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if not all(receipt[k] for k in ('passed', 'programming_verified', 'cold_boot_user_confirmed', 'ready_observed', 'qspi_reset_verified')):
        raise ValueError('缺少本版本QSPI编程或启动证据')
    if receipt['boot_mode'] != 1 or receipt['cold_boot_jtag_download_used']:
        raise ValueError('不能以JTAG下载替代QSPI启动')
    old = ROOT/'releases/latest'
    previous = json.loads((old/'manifest.json').read_text(encoding='utf-8'))
    for name, expected in previous['files'].items():
        if row(old/name) != expected:
            raise ValueError('原发布变化：'+name)
    for name, digest in receipt['evidence'].items():
        path = (ROOT/name).resolve(); path.relative_to(ROOT)
        if row(path)['sha256'] != digest:
            raise ValueError('QSPI证据变化：'+name)
    runtime = json.loads((old/'runtime500/manifest.json').read_text(encoding='utf-8'))
    if runtime['build_id'] != receipt['build_id']:
        raise ValueError('QSPI和当前JTAG不是同一版本')
    for name in ('BOOT.BIN', 'fsbl.elf'):
        if row(image_dir/name) != receipt['inputs'][name]:
            raise ValueError('镜像或FSBL与实板证据不符：'+name)
    for source, name in [('hardware/ecg_system_candidate.bit', 'ecg_system_candidate.bit'), ('prebuilt/ecg_runtime500.elf', 'ecg_runtime500.elf')]:
        if row(old/'runtime500'/source) != receipt['inputs'][name]:
            raise ValueError('运行时和启动镜像的输入不一致')
    output = Path(output).resolve(); output.relative_to(ROOT/'tmp')
    if output.exists():
        raise FileExistsError(output)
    shutil.copytree(old, output, ignore=lambda directory, names: ['qspi'] if Path(directory) == old else [])
    qspi = output/'qspi'; qspi.mkdir()
    for name in ('BOOT.BIN', 'fsbl.elf'):
        shutil.copyfile(image_dir/name, qspi/name)
    (qspi/'boot.bif').write_text('the_ROM_image:\n{\n  [bootloader] fsbl.elf\n  ../runtime500/hardware/ecg_system_candidate.bit\n  ../runtime500/prebuilt/ecg_runtime500.elf\n}\n', encoding='ascii')
    for name in ('program_qspi.ps1', 'probe_qspi.tcl', 'reset_qspi.tcl'):
        shutil.copyfile(ROOT/'board/runtime_handoff'/name, qspi/name)
    components = {role: dict(path=name, **row(output/name)) for role,name in [('fsbl','qspi/fsbl.elf'), ('bit','runtime500/hardware/ecg_system_candidate.bit'), ('app','runtime500/prebuilt/ecg_runtime500.elf')]}
    seal(qspi, build_id=receipt['build_id'], flash_type='qspi-x4-single', offset=0, capacity_bytes=33554432,
         boot_sha256=receipt['boot_sha256'], components=components, programming_verified=True, cold_boot_verified=True)
    artifacts = json.loads((old/'artifacts.json').read_text(encoding='utf-8'))
    artifacts['version'] = VERSION
    artifacts['scope']['flash'] = True
    artifacts['qspi_receipt'] = receipt_path.relative_to(ROOT).as_posix()
    artifacts['qspi_build'] = dict(build_id=receipt['build_id'], boot_sha256=receipt['boot_sha256'], components=components,
                                 programming_verified=True, cold_boot_verified=True, actual_input='saved CSV', real_wireless=False)
    artifacts['evidence'].update({receipt_path.relative_to(ROOT).as_posix(): row(receipt_path)['sha256'], **receipt['evidence']})
    for name in ('program_qspi.ps1', 'probe_qspi.tcl', 'reset_qspi.tcl'):
        artifacts['sources']['qspi/'+name] = dict(source='board/runtime_handoff/'+name, **row(qspi/name))
    (output/'artifacts.json').write_text(json.dumps(artifacts, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    text = (old/'README.md').read_text(encoding='utf-8')
    text = text.replace('# ECG系统JTAG交付', '# ECG系统JTAG与QSPI交付', 1)
    text = text.split('\n\n## QSPI掉电保存',1)[0]
    text = text.replace('也没有Flash固化。', 'QSPI固化及独立证据见下节。')
    text += '''

## QSPI掉电保存

qspi/包含匹配BOOT.BIN、FSBL、BIF和编程/复位脚本；与runtime500共享同版bit/ELF，不重复复制硬件。镜像顺序为FSBL→bit→应用。

本版镜像已在本机板卡完成写入校验、用户彻底断电后QSPI启动及数字CSV回放；不代表接手者的板卡已写入。已经写好本版Flash的板卡，将BOOT_CFG设为1=ON、2=OFF后彻底断电上电即可运行。每轮结束后按PS复位键建立新会话，无需反复写Flash或JTAG下载。

给另一块匹配领航者板卡编程前，先核对具体硬件和唯一下载器，切为JTAG启动并彻底掉电上电；用qspi/program_qspi.ps1显式指定-Program、-Xsdb、-ProgramFlash和-CableSerial才写入。默认或-CheckOnly只验证本地文件，不连接板卡。该操作覆盖偏移0的旧启动镜像，只擦除镜像区域，不整片擦除。

无原构建工作区也能用board/prepare_qspi.py --release releases/latest --bootgen <Bootgen路径> --output tmp/boot_new重新打包；详见docs/download_guide.md和report/交接.md。QSPI编程、校验、系统复位和冷启动是分别验证的阶段，证据见artifacts.json，不继承为真实无线或CNN通过。
'''
    (output/'README.md').write_text(text, encoding='utf-8')
    seal(output, purpose='matched JTAG/QSPI artifacts; formal sources and evidence stay in repository', flash_programming='PROGRAM_VERIFY_AND_COLD_BOOT_PASS')
    print(output)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('image-dir','receipt','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    package(args.image_dir,args.receipt,args.output)
