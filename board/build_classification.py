"""独立构建ARM分类接口自检；复用已验smoke硬件，不连接板卡。"""
import hashlib
import json
import os
from pathlib import Path
import uuid
import vitis
ROOT=Path(__file__).resolve().parents[1]
workspace=Path(os.environ.get('ECG_CLASS_WORKSPACE',str(ROOT/'tmp/classification_20261023/vitis_workspace'))).resolve()
workspace.relative_to(ROOT/'tmp')
if workspace.exists():raise FileExistsError('工作区已存在，请选新的tmp目录')
if any(ord(c)<33 or ord(c)>126 for c in str(workspace)):raise ValueError('工作区须无空格英文路径')
kit=ROOT/'releases/latest/smoke';hardware=kit/'hardware'
man=json.loads((kit/'manifest.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[hardware/n for n in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl')]
for p in artifacts:
 row=man['files'][p.relative_to(kit).as_posix()]
 if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('硬件清单不符：'+str(p))
sources=[ROOT/'src/ps/ecg_classification_smoke/main.c',ROOT/'src/ps/ecg_classification/classification.c',ROOT/'src/ps/ecg_classification/classification.h']
hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sources}
build_id=uuid.uuid4().hex[:16]
client=vitis.create_client()
try:
 client.set_workspace(str(workspace))
 platform=client.create_platform_component(name='ecg_platform',hw_design=str(hardware/'ecg_system_candidate.xsa'),os='standalone',cpu='ps7_cortexa9_0',domain_name='standalone_ps7_cortexa9_0')
 platform.build()
 app=client.create_app_component(name='ecg_classification_smoke',platform=client.find_platform_in_repos('ecg_platform'),domain='standalone_ps7_cortexa9_0',template='empty_application')
 for p in sources:app.import_files(from_loc=str(p.parent),files=[p.name])
 component=workspace/'ecg_classification_smoke'
 (component/'class_build.h').write_text('#define ECG_CLASS_BUILD_ID "'+build_id+'"\n',encoding='ascii')
 app.build()
 elf=component/'build/ecg_classification_smoke.elf'
 if not elf.is_file():raise FileNotFoundError(elf)
 for p in sources:
  if sha(component/p.name)!=hashes[p.relative_to(ROOT).as_posix()]:raise ValueError('构建副本变更')
 paths=artifacts+[elf]
 output={'build_id':build_id,'sources':hashes,'files':{p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths},'scope':'ARM tensor queue only; no QRS/CNN/Flash','elf':elf.relative_to(ROOT).as_posix()}
 (workspace/'build_manifest.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
 print('ECG_CLASS_BUILD_PASS '+str(elf),flush=True)
finally:vitis.dispose()
