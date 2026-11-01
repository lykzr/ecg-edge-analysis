"""离线核对精简JTAG/QSPI发布；不连接板卡，证据/源码在仓库中核对。"""
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
    # 原始收据保留产生时路径；迁移只改变证据位置。
    if name.startswith("docs/records/"):
        p = PurePosixPath(name.replace("docs/records/", "docs/evidence/", 1))
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
        bits=[n for n in z.namelist() if n.endswith('.bit')]
        assert len(bits)==1 and z.read(bits[0]) == (hardware / 'ecg_system_candidate.bit').read_bytes()
    elf = base / 'prebuilt' / {'smoke':'ecg_smoke.elf','bridge':'ecg_bridge.elf','runtime500':'ecg_runtime500.elf'}[sub]
    blob = elf.read_bytes()
    assert blob[:4] == b'\x7fELF' and blob[4] == 1 and blob[5] == 1
    assert int.from_bytes(blob[18:20], 'little') == 40
    return manifest


def check(directory, repository, *, require_current_sources=True):
    directory = Path(directory).resolve()
    repository = Path(repository).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['version'] == '20261101-runtime500-session-reuse-v1':
        from check_session_release import check as check_session_release
        return check_session_release(directory, repository, require_current_sources=require_current_sources)
    assert manifest['version'] in ('20261021-system-jtag-v1','20261024-runtime500-jtag-v1','20261025-runtime500-jtag-v2','20261025-runtime500-qspi-v1')
    qspi_release=manifest['version']=='20261025-runtime500-qspi-v1'
    assert manifest['flash_programming'] == ('PROGRAM_VERIFY_AND_COLD_BOOT_PASS' if qspi_release else 'NOT_PERFORMED')
    check_files(directory, manifest)

    artifacts = json.loads((directory / 'artifacts.json').read_text(encoding='utf-8'))
    assert artifacts['version'] == manifest['version']
    assert not any(artifacts['scope'][k] for k in ('wireless', 'manual_gui', 'ecg_accuracy', 'cnn_int8_pl'))
    assert artifacts['scope']['flash'] is qspi_release
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

    source_drift=[]
    def source_hash(name, expected):
        path=safe(repository,name)
        assert path.is_file(), '仓库来源缺失：'+name
        actual=digest(path)
        if actual!=expected:
            source_drift.append(dict(path=name,expected=expected,actual=actual))
            if require_current_sources:raise AssertionError('当前源码不同于冻结发布：'+name)
    runtime500=None
    if manifest['version'] in ('20261024-runtime500-jtag-v1','20261025-runtime500-jtag-v2','20261025-runtime500-qspi-v1'):
        runtime500=check_subset(directory,'runtime500')
        build=artifacts['runtime500_build']
        assert runtime500['sampling_hz']==500 and runtime500['window_trace'] is False
        assert runtime500['board_execution']=='FINITE_DIGITAL_BOARD_PASS' and runtime500['flash_programming']=='NOT_PERFORMED'
        assert build['build_id']==runtime500['build_id'] and build['window_trace'] is False
        assert build['source_sha256']==runtime500['source_sha256']
        assert build['elf_sha256']==runtime500['elf_sha256']==digest(directory/'runtime500/prebuilt/ecg_runtime500.elf')
        assert build['bit_sha256']==digest(directory/'runtime500/hardware/ecg_system_candidate.bit')
        assert build['xsa_sha256']==digest(directory/'runtime500/hardware/ecg_system_candidate.xsa')
        assert artifacts['scope']['runtime500']=='FINITE_DIGITAL_BOARD_PASS'
        is_vendor=manifest['version'] in ('20261025-runtime500-jtag-v2','20261025-runtime500-qspi-v1')
        receipt_name='data/results/runtime500_release_20261025.json' if is_vendor else 'data/results/runtime500_board_20261024.json'
        if is_vendor:assert artifacts['runtime500_receipt']==receipt_name
        assert receipt_name in artifacts['evidence']
        receipt=json.loads(safe(repository,receipt_name).read_text(encoding='utf-8'))
        assert receipt['passed'] and receipt['production_build_id']==build['build_id']
        assert receipt['production_elf_sha256']==build['elf_sha256'] and receipt['flash_programming']=='NOT_PERFORMED'
        if is_vendor:
            assert runtime500['adc_source_supported'] and build['adc_source_supported']
            assert runtime500['accepted_sources']==['REPLAY','SYNTH','ADC']
            assert receipt['kind']=='vendor500_digital_board' and receipt['adc_source_supported']
            assert not receipt['real_wireless'] and not receipt['calibrated'] and not receipt['accuracy_evaluated']
            for name,source in [('board_csv','REPLAY'),('board_simulated_adc','ADC')]:
                result=receipt['cases'][name]
                assert result['passed'] and result['samples']==result['confirmed']==result['echoed']==10412
                assert result['events']==26 and result['clipped']==0 and result['source']==source
                assert result['pending_bytes']==result['incomplete_rx_bytes']==0
                raw=safe(repository,result['logs']['uart']).read_bytes()
                assert raw.endswith(b'\n')
                fields=[line.decode('ascii').split(',') for line in raw.splitlines()]
                header=fields[0];assert header[0:3]==['H','ECG-UART-1','ps-runtime500-1'] and header[4:]==[source,'QRS26-500-ARM','500','4096','0xD']
                total=0;events=[]
                for f in fields:
                    if f[0]=='W':
                        assert int(f[1])==total and len(f)==3+2*int(f[2])
                        assert all(f[i]=='NA' for i in range(4,len(f),2));total+=int(f[2])
                    if f[0]=='E':events.append(f)
                    if f[0]=='T':assert f[4:9]==['NA','500','0','-1','0']
                assert total==10412 and len(events)==26
                for i,f in enumerate(events):
                    assert int(f[1])==i+1 and int(f[3])==(0 if i==0 else int(f[2])-int(events[i-1][2])) and f[5:]==['?','-1']
                assert raw.splitlines()[-1]==b'L,I,END reason=completed samples=10412 events=26'
                assert 'ECG_CLASS_JTAG_STARTED' in safe(repository,result['logs']['jtag']).read_text(errors='replace')
            assert receipt['cases']['board_csv']['normalized_sha256']==receipt['cases']['board_simulated_adc']['normalized_sha256']
            for name,h in receipt['evidence'].items():assert digest(safe(repository,name))==h,name
        else:
            for name,total in [('record100_debug',15000),('record105_debug',60000),('synth240',60000),('recovery',1500)]:
                result=receipt['cases'][name]
                assert result['passed'] and result['samples']==total and result['confirmed']==total and result['echoed']==total
                assert result['pending_bytes']==0 and result['incomplete_rx_bytes']==0
            assert receipt['cases']['record100_debug']['windows_compared']>0 and receipt['cases']['record100_debug']['max_window_absolute_error']<=1e-6
            assert receipt['cases']['record105_debug']['windows_compared']>0 and receipt['cases']['record105_debug']['max_window_absolute_error']<=1e-6
            assert receipt['faults']['passed'] and len(receipt['faults']['rows'])==3
            assert all(r['passed'] and r['accepted']==0 for r in receipt['faults']['rows'])
        for name,h in runtime500['source_sha256'].items():source_hash(name,h)

    for name, row in artifacts['sources'].items():
        path = safe(directory, name)
        assert path.stat().st_size == row['bytes']
        assert digest(path) == row['sha256'], name
        source = safe(repository, row['source'])
        assert source.is_file(), '仓库来源缺失：' + row['source']
        source_hash(row['source'],row['sha256'])

    for name, expected in artifacts['evidence'].items():
        path = safe(repository, name)
        assert path.is_file(), '证据缺失：' + name
        assert digest(path) == expected, '证据哈希不符：' + name

    for sub in ('smoke', 'bridge'):
        for name, expected in json.loads((directory / sub / 'manifest.json').read_text(encoding='utf-8')).get('source_sha256', {}).items():
            source_hash(name,expected)

    if qspi_release:
        import struct
        qspi=directory/'qspi';qm=json.loads((qspi/'manifest.json').read_text(encoding='utf-8'))
        check_files(qspi,qm)
        receipt_name=artifacts['qspi_receipt'];assert receipt_name=='data/results/qspi_20261025.json'
        qr=json.loads(safe(repository,receipt_name).read_text(encoding='utf-8'))
        assert qr['passed'] and qr['programming_verified'] and qr['cold_boot_user_confirmed'] and qr['ready_observed']
        assert qr['boot_mode']==1 and not qr['cold_boot_jtag_download_used'] and qr['qspi_reset_verified']
        assert qr['formal_bootgen_rebuild_byte_identical']
        assert qm['offset']==qr['offset']==0 and qm['flash_type']==qr['flash_type']=='qspi-x4-single'
        assert qm['build_id']==qr['build_id']==runtime500['build_id']
        assert qm['programming_verified'] and qm['cold_boot_verified']
        assert digest(qspi/'BOOT.BIN')==qr['boot_sha256']==qm['boot_sha256']==artifacts['qspi_build']['boot_sha256']
        blob=(qspi/'BOOT.BIN').read_bytes()
        assert len(blob)==qr['image_bytes']<=qm['capacity_bytes']==33554432
        assert struct.unpack_from('<II',blob,0x20)==(0xAA995566,0x584C4E58)
        for role,component in qm['components'].items():
            path=safe(directory,component['path'])
            assert path.stat().st_size==component['bytes'] and digest(path)==component['sha256']
        assert qm['components']['fsbl']['sha256']==qr['inputs']['fsbl.elf']['sha256']
        assert qm['components']['app']['sha256']==runtime500['elf_sha256']
        assert qm['components']['bit']['sha256']==digest(directory/'runtime500/hardware/ecg_system_candidate.bit')
        assert qr['replay']['passed'] and qr['replay']['confirmed']==qr['replay']['echoed']==10412 and qr['replay']['events']==26
        for name,h in qr['evidence'].items():assert digest(safe(repository,name))==h,name

    assert not any((directory / p).exists() for p in ('BOOT.BIN', 'boot.bif', 'fsbl.elf', 'hello_world.elf'))
    cases = check_board_evidence(repository)
    return {
        'passed': True,
        'check_mode': 'strict_current_sources' if require_current_sources else 'frozen_artifacts_and_evidence',
        'current_sources_match': not source_drift,
        'current_rebuild_qualified': not source_drift,
        'source_drift': source_drift,
        'version': manifest['version'],
        'files': len(manifest['files']) + 1,
        'smoke_files': len(smoke['files']),
        'bridge_files': len(bridge['files']),
        'evidence_checked': len(artifacts['evidence']),
        'sources_checked': len(artifacts['sources']),
        'runtime500': runtime500 is not None,
        'qspi': qspi_release,
        'cases': cases,
        'hardware_operated': False,
        'scope': 'offline release artifacts/evidence; current source identity separately reported; artifact-only success does not qualify current-source rebuild or a new release',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT / 'releases/latest')
    parser.add_argument('--repository', type=Path, default=ROOT)
    parser.add_argument('--artifacts-only',action='store_true',help='仅验冻结产物/证据，仍报告当前源码差异；不授予当前重建或新发布资格')
    args = parser.parse_args()
    print(json.dumps(check(args.directory, args.repository, require_current_sources=not args.artifacts_only), ensure_ascii=False))
