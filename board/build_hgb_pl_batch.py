"""用新PL候选XSA构建整段分类及同精度ARM对比应用；不自动连接板卡。"""
import hashlib,json,os,re,sys
from pathlib import Path
import vitis
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build'))
from export_hgb import export
from build_hgb_legacy import build as legacy_build
workspace=Path(os.environ['ECG_HGB_WORKSPACE']).resolve();workspace.relative_to(ROOT/'tmp')
kind=os.environ.get('ECG_HGB_APP','batch')
if kind!='batch':raise ValueError('PL整段构建仅支持batch；独立固定特征自检使用build_hgb_pl_test.py')
fixture=None
if workspace.exists():raise FileExistsError(workspace)
hardware=Path(os.environ['ECG_HGB_PL_HARDWARE']).resolve();hardware.relative_to(ROOT/'tmp')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[hardware/n for n in ('hgb_pl.bit','hgb_pl.xsa')]
assert all(p.is_file() for p in artifacts)
params=export(workspace.parent/(workspace.name+'_parameters'))
core=ROOT/'src/ps/ecg_hgb';native=ROOT/'model/inference/native'
sources=[core/n for n in ('hgb.h','features.c','pl_tree.c','prepare.c','frozen.h')]+[core/('board_test.c' if kind=='test' else 'pl_main.c')]
sources += [native/n for n in ('pipeline500.c','pipeline.h','rate500.c','rate500.h','window500.h','coefficients.h','classification.c','classification.h','runtime500_bridge.c','runtime.h')]
sources += [workspace.parent/(workspace.name+'_parameters')/'hgb_parameters.c']
if fixture:sources += [fixture/'hgb_fixture.c',fixture/'hgb_fixture.h']
rom=Path(os.environ['ECG_HGB_PL_ROM']).resolve();rom.relative_to(ROOT/'tmp')
sources += [rom/'hgb_pl_fixture.c',rom/'hgb_pl_fixture.h']
hashes={p.as_posix():sha(p) for p in sources}
legacy_sources={};legacy_commands=[];archive=None
if kind=='batch':
    compiler=Path(os.environ['ECG_ARM_GCC'])
    archive,legacy_sources,legacy_commands=legacy_build(workspace.parent/(workspace.name+'_legacy'),compiler)
    sources.append(core/'legacy.h');hashes[(core/'legacy.h').as_posix()]=sha(core/'legacy.h')
client=vitis.create_client()
try:
    client.set_workspace(str(workspace))
    platform=client.create_platform_component(name='ecg_platform',hw_design=str(hardware/'hgb_pl.xsa'),os='standalone',cpu='ps7_cortexa9_0',domain_name='standalone_ps7_cortexa9_0')
    platform.build()
    app=client.create_app_component(name='ecg_hgb_test',platform=client.find_platform_in_repos('ecg_platform'),domain='standalone_ps7_cortexa9_0',template='empty_application')
    for p in sources:app.import_files(from_loc=str(p.parent),files=[p.name])
    component=workspace/'ecg_hgb_test';config=component/'src/UserConfig.cmake'
    text=config.read_text();text=text.replace('set(USER_COMPILE_OPTIMIZATION_LEVEL -O0)','set(USER_COMPILE_OPTIMIZATION_LEVEL -O2)')
    flags='-DECG_HGB_PL -ffp-contract=off -fno-fast-math -fstack-usage -include '+(component/'frozen.h').as_posix()
    text=text.replace('set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS )','set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS "'+flags+'")')
    libraries='"hgb_legacy" "m"' if archive else '"m"'
    text,n=re.subn(r'set\(USER_LINK_LIBRARIES\s*.*?\)','set(USER_LINK_LIBRARIES '+libraries+')',text,count=1,flags=re.S);assert n==1
    if archive:
        text,n=re.subn(r'set\(USER_LINK_DIRECTORIES\s*.*?\)','set(USER_LINK_DIRECTORIES "'+archive.parent.as_posix()+'")',text,count=1,flags=re.S);assert n==1
    text,n=re.subn(r'set\(USER_LINK_OTHER_FLAGS\s*.*?\)','set(USER_LINK_OTHER_FLAGS "-Wl,-Map=ecg_hgb_test.map")',text,count=1,flags=re.S);assert n==1
    config.write_text(text)
    linker=component/'src/lscript.ld';text=linker.read_text();text,n=re.subn(r'(_STACK_SIZE\s*=.*?:\s*)0x[0-9a-fA-F]+',r'\g<1>0x40000',text,count=1);assert n==1;linker.write_text(text)
    app.build()
    elf=component/'build/ecg_hgb_test.elf';link_map=elf.with_name('ecg_hgb_test.map')
    assert elf.is_file() and link_map.is_file()
    for p in sources:assert sha(component/p.name)==hashes[p.as_posix()],p.name
    fsbl=workspace/'ecg_platform/zynq_fsbl/build/fsbl.elf'
    assert fsbl.is_file()
    result=dict(application=kind,dual_protocol=kind=='batch',model=params,elf=elf.relative_to(ROOT).as_posix(),files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in artifacts+[elf,link_map,fsbl]},sources={**{p.relative_to(ROOT).as_posix():h for p,h in ((Path(k),v) for k,v in hashes.items())},**legacy_sources},legacy_commands=legacy_commands,stack_bytes=0x40000,scope='ARM preprocessing + PL trees + same-Q40 ARM comparison '+kind+'; batch model plus existing QRS input; not continuous model scheduling or Flash')
    (workspace/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS HGB_BUILD '+str(elf),flush=True)
finally:vitis.dispose()
