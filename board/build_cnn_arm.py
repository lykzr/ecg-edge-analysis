"""用已验领航者硬件构建H27浮点ARM应用；不下载，不训练。"""
import hashlib,json,os,re,sys
from pathlib import Path
import vitis
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build'))
from build_hgb_legacy import build as legacy_build
from export_hgb import export as export_hgb
workspace=Path(os.environ['ECG_CNN_WORKSPACE']).resolve();workspace.relative_to(ROOT/'tmp')
kind='batch'

fixture=None
if workspace.exists():raise FileExistsError(workspace)
hardware=Path(os.environ['ECG_CNN_HARDWARE']).resolve();hardware.relative_to(ROOT/'tmp')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pl=os.environ.get('ECG_CNN_PL','0')=='1'
int8=os.environ.get('ECG_CNN_INT8','0')=='1'
activity=os.environ.get('ECG_ACTIVITY_LED','0')=='1'
int8_fast=os.environ.get('ECG_CNN_INT8_FAST','0')
if int8_fast not in ('0','4','16'):raise ValueError('INT8_FAST仅允许0/4/16')
if int8_fast!='0' and not (int8 and activity):raise ValueError('INT8快核需要三核工作灯候选')
if activity and not pl:raise ValueError('工作灯仅用于带AXI GPIO的PL候选')
if int8 and not pl:raise ValueError('INT8候选需要保留FP32/HGB的PL镜像')
bitname='cnn_pl' if pl else 'hgb_pl'
artifacts=[hardware/(bitname+ext) for ext in ('.bit','.xsa')]
assert all(p.is_file() for p in artifacts)
params=json.loads((Path(os.environ['ECG_CNN_PARAMETERS'])/'export.json').read_text())
core=ROOT/'src/ps/ecg_hgb';native=ROOT/'model/inference/native';cnn=ROOT/'src/ps/ecg_cnn'
sources=[core/n for n in ('hgb.h','prepare.c','frozen.h','legacy.h')]
sources += [cnn/n for n in ('cnn.h','network.c','features.c','main.c','stream.h','stream.c','stream_uart.h')]
if pl:
    sources += [cnn/'pl_forward.c']+[core/n for n in ('features.c','pl_tree.c','pl_main.c')]
    export_hgb(workspace.parent/(workspace.name+'_hgb_parameters'))
    sources += [workspace.parent/(workspace.name+'_hgb_parameters')/'hgb_parameters.c']
    hgbrom=Path(os.environ['ECG_HGB_PL_ROM']).resolve();hgbrom.relative_to(ROOT/'tmp')
    sources += [hgbrom/'hgb_pl_fixture.c',hgbrom/'hgb_pl_fixture.h']
sources += [native/n for n in ('pipeline500.c','pipeline.h','rate500.c','rate500.h','window500.h','coefficients.h','classification.c','classification.h','runtime500_bridge.c','runtime.h')]
rom=Path(os.environ['ECG_CNN_PARAMETERS']).resolve();rom.relative_to(ROOT/'tmp')
sources += [rom/'cnn_weights.c',rom/'cnn_offsets.h']
if int8:
    qrom=Path(os.environ['ECG_CNN_INT8_PARAMETERS']).resolve();qrom.relative_to(ROOT/'tmp')
    sources += [cnn/'int8_arm.cpp',ROOT/'src/hls/ecg_cnn_int8/int8_core.h',qrom/'cnn_int8_weights.h']
if pl:
    generated=workspace.parent/(workspace.name+'_sources');generated.mkdir(exist_ok=False)
    (generated/'cnn_features.c').write_bytes((cnn/'features.c').read_bytes())
    sources=[generated/'cnn_features.c' if p==cnn/'features.c' else p for p in sources]
    if activity:
        # 原main.c保持封印；候选将全部会话入口统一包裹，返回即熄灭。
        main_text=(cnn/'main.c').read_text(encoding='utf-8')
        old='    ready();\n    for(;;)'
        assert main_text.count(old)==1
        main_text=main_text.replace(old,'    activity_init();\n'+old)
        old='            if(hgb_legacy_run(text,NULL,legacy_clock,legacy_receive,legacy_ready,legacy_send))return 4;'
        assert main_text.count(old)==1
        main_text=main_text.replace(old,'            activity_set(1);\n            int legacy_rc=hgb_legacy_run(text,NULL,legacy_clock,legacy_receive,legacy_ready,legacy_send);\n            activity_set(0);\n            if(legacy_rc)return 4;')
        for call in ('stream_session(f,nf)','hgb_batch_session(f,nf)','session(f,nf)'):
            old='(void)'+call+';'
            assert old in main_text
            main_text=main_text.replace(old,'activity_set(1);'+old+'activity_set(0);')
        (generated/'cnn_activity_main.c').write_text('#include "activity_led.h"\n'+main_text,encoding='utf-8')
        sources=[generated/'cnn_activity_main.c' if p==cnn/'main.c' else p for p in sources]
        sources += [cnn/'activity_led.h']
hashes={p.as_posix():sha(p) for p in sources}
if pl:hashes[(cnn/'features.c').as_posix()]=sha(cnn/'features.c')
if activity:hashes[(cnn/'main.c').as_posix()]=sha(cnn/'main.c')
if activity:
    # 下载前同时核对候选硬件源码与导出ROM，旧交付封印不改。
    inputs=[ROOT/n for n in ('build/build_cnn_fast_pl.tcl','build/export_cnn_fast.py',
        'build/build_navigator_ecg_system.tcl','src/hls/ecg_cnn_fast/cnn_hls.cpp',
        'src/hls/ecg_cnn_int8/cnn_int8_hls.cpp','src/rtl/ecg_activity_led.sv',
        'src/constraints/activity_led_navigator_v2.xdc')]
    inputs += [rom.parent/n for n in ('cnn_hls_weights.h','cnn_dense_fast_weights.h')]
    hashes.update({p.as_posix():sha(p) for p in inputs})
if int8_fast!='0':
    inputs=[ROOT/n for n in ('build/build_cnn_int8_fast_pl.tcl','build/export_cnn_int8_fast.py',
        'src/hls/ecg_cnn_int8_fast/int8_fast_core.h','src/hls/ecg_cnn_int8_fast/cnn_int8_hls.cpp')]
    inputs += [qrom/'cnn_int8_fast_weights.h']
    if int8_fast=='16':
        inputs += [ROOT/'src/hls/ecg_cnn_int8_fast/cnn_int8_conv16.cpp',
            ROOT/'src/hls/ecg_cnn_int8_fast/int8_conv16.h',qrom/'cnn_int8_conv16_weights.h']
    hashes.update({p.as_posix():sha(p) for p in inputs})
legacy_sources={};legacy_commands=[];archive=None
if kind=='batch':
    compiler=Path(os.environ['ECG_ARM_GCC'])
    archive,legacy_sources,legacy_commands=legacy_build(workspace.parent/(workspace.name+'_legacy'),compiler)
    sources.append(core/'legacy.h');hashes[(core/'legacy.h').as_posix()]=sha(core/'legacy.h')
client=vitis.create_client()
try:
    client.set_workspace(str(workspace))
    platform=client.create_platform_component(name='ecg_platform',hw_design=str(hardware/(bitname+'.xsa')),os='standalone',cpu='ps7_cortexa9_0',domain_name='standalone_ps7_cortexa9_0')
    platform.build()
    app=client.create_app_component(name='ecg_cnn_arm',platform=client.find_platform_in_repos('ecg_platform'),domain='standalone_ps7_cortexa9_0',template='empty_application')
    for p in sources:app.import_files(from_loc=str(p.parent),files=[p.name])
    component=workspace/'ecg_cnn_arm';config=component/'src/UserConfig.cmake'
    text=config.read_text();text=text.replace('set(USER_COMPILE_OPTIMIZATION_LEVEL -O0)','set(USER_COMPILE_OPTIMIZATION_LEVEL -O2)')
    flags=('-DECG_CNN_PL -DECG_HGB_PL -DECG_DUAL_MODEL ' if pl else '')+'-ffp-contract=off -fno-fast-math -fstack-usage -include '+(component/'frozen.h').as_posix()
    if int8:flags='-DECG_CNN_INT8 '+flags
    text=text.replace('set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS )','set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS "'+flags+'")')
    libraries='"hgb_legacy" "m"' if archive else '"m"'
    text,n=re.subn(r'set\(USER_LINK_LIBRARIES\s*.*?\)','set(USER_LINK_LIBRARIES '+libraries+')',text,count=1,flags=re.S);assert n==1
    if archive:
        text,n=re.subn(r'set\(USER_LINK_DIRECTORIES\s*.*?\)','set(USER_LINK_DIRECTORIES "'+archive.parent.as_posix()+'")',text,count=1,flags=re.S);assert n==1
    text,n=re.subn(r'set\(USER_LINK_OTHER_FLAGS\s*.*?\)','set(USER_LINK_OTHER_FLAGS "-Wl,-Map=ecg_cnn_arm.map")',text,count=1,flags=re.S);assert n==1
    config.write_text(text)
    if int8:
        cmake=component/'src/CMakeLists.txt';mixed=cmake.read_text()
        # Vitis按cpp扩展名把整个工程标成c++，模板会错误改写C编译器。
        assert 'set(CMAKE_C_COMPILER ${CMAKE_CXX_COMPILER})' in mixed
        mixed=mixed.replace('set(CMAKE_C_COMPILER ${CMAKE_CXX_COMPILER})','# 保留C编译器；仅.cpp使用C++编译器')
        cmake.write_text(mixed)
    linker=component/'src/lscript.ld';text=linker.read_text();text,n=re.subn(r'(_STACK_SIZE\s*=.*?:\s*)0x[0-9a-fA-F]+',r'\g<1>0x40000',text,count=1);assert n==1;linker.write_text(text)
    app.build()
    elf=component/'build/ecg_cnn_arm.elf';link_map=elf.with_name('ecg_cnn_arm.map')
    assert elf.is_file() and link_map.is_file()
    for p in sources:assert sha(component/p.name)==hashes[p.as_posix()],p.name
    fsbl=workspace/'ecg_platform/zynq_fsbl/build/fsbl.elf';init=workspace/'ecg_platform/hw/sdt/ps7_init.tcl'
    assert fsbl.is_file() and init.is_file()
    result=dict(application='cnn_batch',protocol='ECG-DUAL-STREAM-1' if pl else 'CNN-BATCH-1',dual_protocol=True,model=params,elf=elf.relative_to(ROOT).as_posix(),bit=artifacts[0].relative_to(ROOT).as_posix(),init=init.relative_to(ROOT).as_posix(),files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in artifacts+[elf,link_map,fsbl,init]},sources={**{p.relative_to(ROOT).as_posix():h for p,h in ((Path(k),v) for k,v in hashes.items())},**legacy_sources},legacy_commands=legacy_commands,stack_bytes=0x40000,scope='H27 FP32 CNN streaming and batch + HGB batch PL, with per-beat ARM comparison' if pl else 'H27 FP32 ARM CNN; not continuous scheduling or Flash')
    (workspace/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    if int8:
        result['protocol']='ECG-TRIPLE-1';result['quantization']=json.loads((qrom/'export.json').read_text())
        result['scope']='FP32 CNN + W8A8 CNN + HGB; each integer result checked against same-device integer ARM reference'
        (workspace/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    if activity:
        result['activity_led']=dict(pin='H15',active_high=True,gpio_base='0x43C40000',meaning='active board session, not per-cycle CNN busy')
        (workspace/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    if int8_fast!='0':
        result['int8_acceleration']=dict(dense_output_lanes=4,conv_output_lanes=16 if int8_fast=='16' else 8,
            same_integer_model=True,arm_reference_unchanged=True)
        (workspace/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS CNN_ARM_BUILD '+str(elf),flush=True)
finally:vitis.dispose()
