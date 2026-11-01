"""用匹配发布XSA构建独立ARM模型数值验收应用；不自动连接板卡。"""
import hashlib,json,os,re,sys
from pathlib import Path
import vitis
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build'))
from export_hgb import export
workspace=Path(os.environ['ECG_HGB_WORKSPACE']).resolve();workspace.relative_to(ROOT/'tmp')
kind=os.environ.get('ECG_HGB_APP','test')
if kind not in ('test','batch'):raise ValueError('ECG_HGB_APP只支持test/batch')
fixture=Path(os.environ['ECG_HGB_FIXTURE']).resolve() if kind=='test' else None
if fixture:fixture.relative_to(ROOT/'tmp')
if workspace.exists():raise FileExistsError(workspace)
hardware=ROOT/'releases/latest/smoke/hardware'
manifest=json.loads((ROOT/'releases/latest/smoke/manifest.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[hardware/n for n in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl')]
for p in artifacts:
    row=manifest['files'][p.relative_to(hardware.parent).as_posix()]
    assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],str(p)
params=export(workspace.parent/(workspace.name+'_parameters'))
core=ROOT/'src/ps/ecg_hgb';native=ROOT/'model/inference/native'
sources=[core/n for n in ('hgb.h','features.c','tree.c','prepare.c','frozen.h')]+[core/('board_test.c' if kind=='test' else 'main.c')]
sources += [native/n for n in ('pipeline500.c','pipeline.h','rate500.c','rate500.h','window500.h','coefficients.h','classification.c','classification.h','runtime500_bridge.c','runtime.h')]
sources += [workspace.parent/(workspace.name+'_parameters')/'hgb_parameters.c']
if fixture:sources += [fixture/'hgb_fixture.c',fixture/'hgb_fixture.h']
hashes={p.as_posix():sha(p) for p in sources}
client=vitis.create_client()
try:
    client.set_workspace(str(workspace))
    platform=client.create_platform_component(name='ecg_platform',hw_design=str(hardware/'ecg_system_candidate.xsa'),os='standalone',cpu='ps7_cortexa9_0',domain_name='standalone_ps7_cortexa9_0')
    platform.build()
    app=client.create_app_component(name='ecg_hgb_test',platform=client.find_platform_in_repos('ecg_platform'),domain='standalone_ps7_cortexa9_0',template='empty_application')
    for p in sources:app.import_files(from_loc=str(p.parent),files=[p.name])
    component=workspace/'ecg_hgb_test';config=component/'src/UserConfig.cmake'
    text=config.read_text();text=text.replace('set(USER_COMPILE_OPTIMIZATION_LEVEL -O0)','set(USER_COMPILE_OPTIMIZATION_LEVEL -O2)')
    flags='-ffp-contract=off -fno-fast-math -fstack-usage -include '+(component/'frozen.h').as_posix()
    text=text.replace('set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS )','set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS "'+flags+'")')
    text,n=re.subn(r'set\(USER_LINK_LIBRARIES\s*.*?\)','set(USER_LINK_LIBRARIES "m")',text,count=1,flags=re.S);assert n==1
    text,n=re.subn(r'set\(USER_LINK_OTHER_FLAGS\s*.*?\)','set(USER_LINK_OTHER_FLAGS "-Wl,-Map=ecg_hgb_test.map")',text,count=1,flags=re.S);assert n==1
    config.write_text(text)
    linker=component/'src/lscript.ld';text=linker.read_text();text,n=re.subn(r'(_STACK_SIZE\s*=.*?:\s*)0x[0-9a-fA-F]+',r'\g<1>0x40000',text,count=1);assert n==1;linker.write_text(text)
    app.build()
    elf=component/'build/ecg_hgb_test.elf';link_map=elf.with_name('ecg_hgb_test.map')
    assert elf.is_file() and link_map.is_file()
    for p in sources:assert sha(component/p.name)==hashes[p.as_posix()],p.name
    result=dict(application=kind,model=params,elf=elf.relative_to(ROOT).as_posix(),files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in artifacts+[elf,link_map]},sources={p.relative_to(ROOT).as_posix():h for p,h in ((Path(k),v) for k,v in hashes.items())},stack_bytes=0x40000,scope='independent ARM '+kind+'; not continuous model scheduling or Flash')
    (workspace/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS HGB_BUILD '+str(elf),flush=True)
finally:vitis.dispose()
