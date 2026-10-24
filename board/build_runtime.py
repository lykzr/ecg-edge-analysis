"""独立构建冻结360Hz QRS及切拍串口应用；复用已验smoke硬件，不连接板卡。"""
import hashlib
import json
import os
from pathlib import Path
import uuid
import re
import runpy
import vitis
ROOT=Path(__file__).resolve().parents[1]
rate=int(os.environ.get('ECG_RUNTIME_RATE','360'))
if rate not in (360,500):raise ValueError('仅支持360/500Hz独立构建')
app_name='ecg_runtime' if rate==360 else 'ecg_runtime500'
workspace=Path(os.environ.get('ECG_RUNTIME_WORKSPACE',str(ROOT/'tmp/system_port_20261024/vitis_workspace'))).resolve()
workspace.relative_to(ROOT/'tmp')
if workspace.exists():raise FileExistsError('工作区已存在，请选新的tmp目录')
if any(ord(c)<33 or ord(c)>126 for c in str(workspace)):raise ValueError('工作区须无空格英文路径')
# 默认保留已验发布组合；完整重建只能显式传入带清单的新硬件目录。
custom=os.environ.get('ECG_RUNTIME_HARDWARE')
if custom:
 hardware=Path(custom).resolve();hardware.relative_to(ROOT/'tmp');kit=hardware.parent
 man=json.loads((hardware/'hardware_manifest.json').read_text(encoding='utf-8'))
else:
 kit=ROOT/'releases/latest/smoke';hardware=kit/'hardware'
 man=json.loads((kit/'manifest.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[hardware/n for n in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl')]
for p in artifacts:
 row=man['files'][p.relative_to(kit).as_posix()]
 if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('硬件清单不符：'+str(p))
sources=[ROOT/'src/ps/ecg_runtime'/n for n in ('main.c','runtime.c','runtime.h','pipeline.c','pipeline.h','resample360.h','link.c','link.h')]+[ROOT/'src/ps/ecg_classification'/n for n in ('classification.c','classification.h')]+[ROOT/'src/ps/ecg_bridge/bridge_time.h']
hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sources}
if rate==500:
 generated=workspace.parent/(workspace.name+'_generated500')
 runpy.run_path(str(ROOT/'build/generate_rate500_runtime.py'))['run'](generated)
 sources=[p for p in sources if p.name not in ('runtime.c','pipeline.c','link.c','resample360.h')]
 sources += [generated/'runtime500_bridge.c',generated/'link500.c']+[ROOT/'src/ps/ecg_rate500'/n for n in ('rate500.c','rate500.h','coefficients.h','pipeline500.c','window500.h')]
 hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
build_id=uuid.uuid4().hex[:16]
client=vitis.create_client()
try:
 client.set_workspace(str(workspace))
 platform=client.create_platform_component(name='ecg_platform',hw_design=str(hardware/'ecg_system_candidate.xsa'),os='standalone',cpu='ps7_cortexa9_0',domain_name='standalone_ps7_cortexa9_0')
 platform.build()
 app=client.create_app_component(name=app_name,platform=client.find_platform_in_repos('ecg_platform'),domain='standalone_ps7_cortexa9_0',template='empty_application')
 for p in sources:app.import_files(from_loc=str(p.parent),files=[p.name])
 component=workspace/app_name
 (component/'class_build.h').write_text('#define ECG_CLASS_BUILD_ID "'+build_id+'"\n',encoding='ascii')
 config=component/'src/UserConfig.cmake'
 text=config.read_text(encoding='utf-8')
 text=text.replace('set(USER_COMPILE_OPTIMIZATION_LEVEL -O0)','set(USER_COMPILE_OPTIMIZATION_LEVEL -O2)')
 text=text.replace('set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS )','set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS -ffp-contract=off)')
 text,count=re.subn(r'set\(USER_LINK_LIBRARIES\s*.*?\)', 'set(USER_LINK_LIBRARIES "m")',text,count=1,flags=re.S)
 if count!=1:raise ValueError('未识别Vitis链接配置')
 # 显式生成链接图，区分编译输入、实际链接对象和未参与的GPL工具输入。
 text,nmap=re.subn(r'set\(USER_LINK_OTHER_FLAGS\s*.*?\)', 'set(USER_LINK_OTHER_FLAGS "-Wl,-Map=ecg_runtime.map")',text,count=1,flags=re.S)
 if nmap!=1:raise ValueError('未识别链接图配置')
 config.write_text(text,encoding='utf-8')
 linker=component/'src/lscript.ld';text=linker.read_text(encoding='utf-8')
 text=text.replace('_STACK_SIZE : 0x2000','_STACK_SIZE : 0x20000')
 linker.write_text(text,encoding='utf-8')
 app.build()
 elf=component/('build/'+app_name+'.elf')
 if not elf.is_file():raise FileNotFoundError(elf)
 for p in sources:
  if sha(component/p.name)!=hashes[p.relative_to(ROOT).as_posix()]:raise ValueError('构建副本变更')
 link_map=component/'build/ecg_runtime.map'
 if not link_map.is_file():raise FileNotFoundError('缺少实际链接图：'+str(link_map))
 paths=artifacts+[elf,link_map]
 output={'build_id':build_id,'sampling_hz':rate,'sources':hashes,'files':{p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths},'scope':('ARM frozen360 QRS/window; no CNN/500Hz/Flash' if rate==360 else 'ARM source500 adapted QRS/window; no final CNN/real AFE/Flash; board pending'),'elf':elf.relative_to(ROOT).as_posix()}
 (workspace/'build_manifest.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
 print('ECG_RUNTIME_BUILD_PASS '+str(elf),flush=True)
finally:vitis.dispose()
