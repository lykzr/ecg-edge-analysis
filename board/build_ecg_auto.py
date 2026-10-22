"""Vitis Python：新建启动学习候选工作区；生成的PS仅变更身份/预热声明，不改旧核心。"""
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
def prepare_sources(sources):
    """生成仅改变身份/预热说明的PS副本；可在无Vitis环境检查。"""
    sources=Path(sources)
    sources.mkdir(parents=True,exist_ok=False)
    origins={}
    for name in ('main.c','bridge.c','bridge.h','bridge_time.h'):
        original=ROOT/'src/ps/ecg_bridge'/name
        text=original.read_text(encoding='utf-8')
        origins[name]=hashlib.sha256(original.read_bytes()).hexdigest()
        if name=='bridge.c':
            assert text.count('ps-bridge-1')==1 and text.count('QRS-ORIG-60')==1
            text=text.replace('ps-bridge-1','ps-auto-1').replace('QRS-ORIG-60','QRS-AUTOPEAK-60')
            anchor='if(!put(s,line)||!ack(s,"READY","NA"))'
            assert text.count(anchor)==1
            # H之后输出预热信息，再发READY；报文不新增字段或混用输入协议。
            text=text.replace(anchor,'if(!put(s,line)||!put(s,"L,I,WARMUP samples=1000 policy=no_events preserve_indices\\n")||!ack(s,"READY","NA"))')
        (sources/name).write_text(text,encoding='utf-8')
    return origins


def main():
    import vitis
    hardware=Path(os.environ['ECG_AUTO_HARDWARE']).resolve()
    workspace=Path(os.environ['ECG_AUTO_WORKSPACE']).resolve()
    workspace.relative_to(ROOT/'tmp')
    if workspace.exists():raise FileExistsError('工作区已存在，不覆盖')
    dependency=workspace/'ecg_platform/ps7_cortexa9_0/standalone_ps7_cortexa9_0/bsp/libsrc/build_configs/gen_bsp/libsrc/standalone/src/CMakeFiles/xilstandalone.dir/arm/cortexa9/gcc/translation_table.S.obj.d'
    if os.name=='nt' and len(str(dependency))>=255:
        raise ValueError('BSP依赖路径过长，请用项目tmp下更短的工作区，例如tmp/ecg_auto/w')
    for name in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl'):
        if not (hardware/name).is_file():raise FileNotFoundError(hardware/name)
    sources=workspace.parent/'generated_ps'
    origins=prepare_sources(sources)
    client=vitis.create_client()
    try:
        client.set_workspace(str(workspace))
        platform=client.create_platform_component(name='ecg_platform',hw_design=str(hardware/'ecg_system_candidate.xsa'),
            os='standalone',cpu='ps7_cortexa9_0',domain_name='standalone_ps7_cortexa9_0')
        platform.build()
        xpfm=workspace/'ecg_platform/export/ecg_platform/ecg_platform.xpfm'
        if not xpfm.is_file():raise RuntimeError('平台未成功导出，请检查前面的BSP构建错误')
        app=client.create_app_component(name='ecg_auto',platform=client.find_platform_in_repos('ecg_platform'),
            domain='standalone_ps7_cortexa9_0',template='empty_application')
        app.import_files(from_loc=str(sources),files=list(origins))
        app.build()
        for name in origins:
            assert (workspace/'ecg_auto'/name).read_bytes()==(sources/name).read_bytes(),name
        app_root=workspace/'ecg_auto'
        for source,target in [('ecg_system_candidate.bit','_ide/bitstream/ecg_system_candidate.bit'),('ps7_init.tcl','_ide/psinit/ps7_init.tcl')]:
            destination=app_root/target;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(hardware/source,destination)
        launch=(ROOT/'releases/latest/smoke/board/launch_template.json').read_text(encoding='utf-8').replace('ecg_smoke','ecg_auto')
        (app_root/'_ide/launch.json').write_text(launch,encoding='utf-8')
        def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
        result=dict(component='ecg_auto',sample_rate_hz=500,warmup_samples=1000,detector='QRS-AUTOPEAK-60',
            original_ps_sha256=origins,generated_ps_sha256={n:sha(sources/n) for n in origins},
            hardware_sha256={n:sha(hardware/n) for n in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl')},
            elf_sha256=sha(app_root/'build/ecg_auto.elf'),scope='built only, no board execution')
        (workspace/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('ECG_AUTO_APP_BUILT',flush=True)
    finally:vitis.dispose()


if __name__=='__main__':main()
