"""Vitis Python：创建独立合成流工作区并构建，不连接板卡，不修改smoke。"""
import hashlib
import json
import os
from pathlib import Path
import uuid
import shutil
import vitis

ROOT = Path(__file__).resolve().parents[1]
component = os.environ.get('ECG_STREAM_APP', 'ecg_stream')
if component not in ('ecg_stream', 'ecg_bridge'):
    raise ValueError('只支持ecg_stream或ecg_bridge')
workspace = Path(os.environ.get('ECG_STREAM_WORKSPACE', str(ROOT/'tmp/ecg_stream_500/vitis_workspace'))).resolve()
hardware = ROOT/'tmp/ecg_stream_500/hardware'
xsa = Path(os.environ.get('ECG_STREAM_XSA', str(hardware/'ecg_system_candidate.xsa'))).resolve()
bit = Path(os.environ.get('ECG_STREAM_BIT', str(hardware/'ecg_system_candidate.bit'))).resolve()
psinit = Path(os.environ.get('ECG_STREAM_PSINIT', str(hardware/'ps7_init.tcl'))).resolve()
if 'ECG_STREAM_XSA' in os.environ and not all(n in os.environ for n in ('ECG_STREAM_BIT','ECG_STREAM_PSINIT')):
    raise ValueError('自定义XSA时必须同时指定匹配的ECG_STREAM_BIT与ECG_STREAM_PSINIT')
total = int(os.environ.get('ECG_STREAM_SAMPLES', '5003'))
if not 1 <= total <= 1800000:
    raise ValueError('ECG_STREAM_SAMPLES必须为1..1800000')
if workspace.exists():
    raise FileExistsError('工作区已存在；用ECG_STREAM_WORKSPACE选择新的英文目录')
if any(ord(c) < 33 or ord(c) > 126 for c in str(workspace)):
    raise ValueError('Vitis工作区使用无空格英文路径')
names = ('main.c', 'stream.c', 'stream.h') if component == 'ecg_stream' else ('main.c', 'bridge.c', 'bridge.h')
sources = [ROOT/'src/ps'/component/n for n in names]
for p in [xsa, bit, psinit, *sources]:
    if not p.is_file(): raise FileNotFoundError(p)
hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
print('ECG_STREAM: starting Vitis client', flush=True)
client = vitis.create_client()
try:
    print('ECG_STREAM: creating workspace '+str(workspace), flush=True)
    client.set_workspace(str(workspace))
    platform = client.create_platform_component(name='ecg_platform', hw_design=str(xsa), os='standalone',
        cpu='ps7_cortexa9_0', domain_name='standalone_ps7_cortexa9_0')
    platform.build()
    app = client.create_app_component(name=component, platform=client.find_platform_in_repos('ecg_platform'),
        domain='standalone_ps7_cortexa9_0', template='empty_application')
    app.import_files(from_loc=str(sources[0].parent), files=[p.name for p in sources])
    build_id = uuid.uuid4().hex[:16]
    (workspace/component/'stream_build.h').write_text(
        f'#define ECG_STREAM_BUILD_ID "{build_id}"\n#define ECG_STREAM_SAMPLES {total}U\n', encoding='ascii')
    app.build()
    for name, expected in hashes.items():
        if hashlib.sha256((workspace/component/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('构建源码发生变化: '+name)
    elf = workspace/component/'build'/(component+'.elf')
    if not elf.is_file(): raise FileNotFoundError(elf)
    for source, target in [(bit, '_ide/bitstream/ecg_system_candidate.bit'), (psinit, '_ide/psinit/ps7_init.tcl')]:
        destination = workspace/component/target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    launch = json.loads((ROOT/'releases/latest/board/launch_template.json').read_text(encoding='utf-8'))
    # 仅修改本次新组件的启动副本，不改已验收smoke启动配置。
    launch = json.loads(json.dumps(launch).replace('ecg_smoke', component))
    (workspace/component/'_ide/launch.json').write_text(json.dumps(launch, indent=2)+'\n', encoding='utf-8')
    manifest = {'component': component, 'build_id': build_id, 'samples': total if component == 'ecg_stream' else None, 'sample_rate_hz': 500, 'source_sha256': hashes,
        'xsa': str(xsa), 'xsa_sha256': hashlib.sha256(xsa.read_bytes()).hexdigest(),
        'bit_sha256': hashlib.sha256(bit.read_bytes()).hexdigest(), 'psinit_sha256': hashlib.sha256(psinit.read_bytes()).hexdigest(),
        'elf': str(elf), 'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
        'scope': 'built only; no board execution or Flash programming'}
    (workspace/'build_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print('ECG_STREAM_BUILD_PASS '+str(elf), flush=True)
finally:
    vitis.dispose()
