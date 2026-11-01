"""会话复用新版发布检查；旧版规则由check_system_release保留。"""
import json
import struct
from check_system_release import check_files, check_subset, digest, safe
from check_board_evidence import check as check_board_evidence

def check(directory, repository, *, require_current_sources=True):
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['version']=='20261101-runtime500-session-reuse-v1'
    assert manifest['flash_programming']=='PROGRAM_VERIFY_COLD_BOOT_AND_SESSION_REUSE_PASS'
    check_files(directory,manifest)
    artifacts=json.loads((directory/'artifacts.json').read_text(encoding='utf-8'))
    assert artifacts['version']==manifest['version']
    assert all(artifacts['scope'][k] is False for k in ('wireless','manual_gui','ecg_accuracy','cnn_int8_pl'))
    assert artifacts['scope']['flash'] is True
    for sub in ('smoke','bridge','runtime500'):check_subset(directory,sub)
    runtime=json.loads((directory/'runtime500/manifest.json').read_text(encoding='utf-8'))
    build=artifacts['runtime500_build']
    assert runtime['build_id']==build['build_id']=='36e807fd28c440f5'
    assert runtime['sampling_hz']==500 and runtime['window_trace'] is False
    assert runtime['session_reuse'] is True
    assert runtime['accepted_sources']==['REPLAY','SYNTH','ADC']
    assert runtime['source_sha256']==build['source_sha256']
    assert runtime['elf_sha256']==build['elf_sha256']==digest(directory/'runtime500/prebuilt/ecg_runtime500.elf')
    assert build['bit_sha256']==digest(directory/'runtime500/hardware/ecg_system_candidate.bit')
    assert build['xsa_sha256']==digest(directory/'runtime500/hardware/ecg_system_candidate.xsa')
    drift=[]
    def source_hash(name,expected):
        actual=digest(safe(repository,name))
        if actual!=expected:
            drift.append(dict(path=name,expected=expected,actual=actual))
            if require_current_sources:raise AssertionError('当前源码不同于冻结发布：'+name)
    for name,h in runtime['source_sha256'].items():source_hash(name,h)
    assert 'src/ps/ecg_runtime/link.c' in runtime['source_sha256']
    for name,row in artifacts['sources'].items():
        path=safe(directory,name)
        assert path.stat().st_size==row['bytes'] and digest(path)==row['sha256']
        source_hash(row['source'],row['sha256'])
    for sub in ('smoke','bridge'):
        meta=json.loads((directory/sub/'manifest.json').read_text(encoding='utf-8'))
        for name,h in meta.get('source_sha256',{}).items():source_hash(name,h)
    for name,h in artifacts['evidence'].items():assert digest(safe(repository,name))==h,name
    receipt_name=artifacts['qspi_receipt']
    assert receipt_name=='data/results/session_reuse_release_20261101.json'
    receipt=json.loads(safe(repository,receipt_name).read_text(encoding='utf-8'))
    assert receipt['passed'] and receipt['build_id']==runtime['build_id']
    assert receipt['programming_verified'] and receipt['cold_boot_user_confirmed']
    assert receipt['boot_mode']==1 and receipt['cold_boot_jtag_download_used'] is False
    assert receipt['qspi_reset_verified'] and receipt['formal_bootgen_rebuild_byte_identical']
    for key in ('jtag_sessions','qspi_sessions'):
        sessions=json.loads(safe(repository,receipt[key]).read_text(encoding='utf-8'))
        assert sessions['build_id']==runtime['build_id'] and sessions['reset_between_sessions'] is False
        assert [s['name'] for s in sessions['sessions']]==['first','longer','manual_stop','after_idle']
        for session in sessions['sessions']:
            info=session['info'];n=info['source_samples']
            assert info['error'] is None and info['done'] is True
            assert n==info['confirmed']==info['echoed']
            assert info['pending_bytes']==info['incomplete_rx_bytes']==0
            assert info['reason']==('stopped_by_user' if session['name']=='manual_stop' else 'completed')
            assert n==dict(first=5000,longer=15000,after_idle=5000).get(session['name'],n)
            if session['name']=='manual_stop':assert 0<n<10000
            events=session['events'];assert events[0][0]==1 and events[0][2]==0
            for prev,event in zip(events,events[1:]):
                assert event[0]==prev[0]+1 and event[2]==event[1]-prev[1]
        assert sessions['sessions'][0]['events']==sessions['sessions'][3]['events']
    assert receipt['cold_boot_completed_sessions']==3
    assert receipt['cold_boot_fourth_session_interrupted'] is True
    for name,h in receipt['evidence'].items():assert digest(safe(repository,name))==h,name
    qm=json.loads((directory/'qspi/manifest.json').read_text(encoding='utf-8'))
    check_files(directory/'qspi',qm)
    assert qm['build_id']==runtime['build_id']
    assert qm['offset']==0 and qm['flash_type']=='qspi-x4-single'
    assert qm['programming_verified'] and qm['cold_boot_verified']
    blob=(directory/'qspi/BOOT.BIN').read_bytes()
    assert len(blob)==receipt['image_bytes']<=qm['capacity_bytes']==33554432
    assert struct.unpack_from('<II',blob,32)==(0xAA995566,0x584C4E58)
    assert digest(directory/'qspi/BOOT.BIN')==qm['boot_sha256']==receipt['boot_sha256']==artifacts['qspi_build']['boot_sha256']
    expected_paths=dict(fsbl='qspi/fsbl.elf',bit='runtime500/hardware/ecg_system_candidate.bit',app='runtime500/prebuilt/ecg_runtime500.elf')
    for role,row in qm['components'].items():
        assert row['path']==expected_paths[role]
        path=safe(directory,row['path'])
        assert path.stat().st_size==row['bytes'] and digest(path)==row['sha256']
        assert row==receipt['components'][role]==artifacts['qspi_build']['components'][role]
    return dict(passed=True,version=manifest['version'],check_mode='strict_current_sources' if require_current_sources else 'frozen_artifacts_and_evidence',
        current_sources_match=not drift,current_rebuild_qualified=not drift,source_drift=drift,files=len(manifest['files'])+1,
        evidence_checked=len(artifacts['evidence']),sources_checked=len(artifacts['sources']),runtime500=True,qspi=True,
        session_reuse=True,cases=check_board_evidence(repository),hardware_operated=False,
        scope='发布文件、匹配来源与既有分阶段证据；不操作板卡，不构成新的实板验收')
