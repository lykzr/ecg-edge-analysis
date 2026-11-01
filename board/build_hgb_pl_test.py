"""由新PL候选XSA构建同精度ARM/PL自检，不下载，不改发布目录。"""
import hashlib,json,os,re
from pathlib import Path
import vitis
ROOT=Path(__file__).resolve().parents[1]
workspace=Path(os.environ['ECG_HGB_PL_WORKSPACE']).resolve()
hardware=Path(os.environ['ECG_HGB_PL_HARDWARE']).resolve()
rom=Path(os.environ['ECG_HGB_PL_ROM']).resolve()
for p in (workspace,hardware,rom):p.relative_to(ROOT/'tmp')
if workspace.exists():raise FileExistsError(workspace)
xsa=hardware/'hgb_pl.xsa'
if not xsa.is_file():raise FileNotFoundError(xsa)
sources=[ROOT/'src/ps/ecg_hgb/pl_test.c',rom/'hgb_pl_fixture.h',rom/'hgb_pl_fixture.c']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
client=vitis.create_client()
try:
    client.set_workspace(str(workspace))
    platform=client.create_platform_component(name='hgb_pl_platform',hw_design=str(xsa),os='standalone',cpu='ps7_cortexa9_0',domain_name='standalone_ps7_cortexa9_0')
    platform.build()
    app=client.create_app_component(name='hgb_pl_test',platform=client.find_platform_in_repos('hgb_pl_platform'),domain='standalone_ps7_cortexa9_0',template='empty_application')
    for p in sources:app.import_files(from_loc=str(p.parent),files=[p.name])
    config=workspace/'hgb_pl_test/src/UserConfig.cmake'
    text=config.read_text().replace('set(USER_COMPILE_OPTIMIZATION_LEVEL -O0)','set(USER_COMPILE_OPTIMIZATION_LEVEL -O2)')
    text=text.replace('set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS )','set(USER_COMPILE_OPTIMIZATION_OTHER_FLAGS "-ffp-contract=off -fno-fast-math")')
    config.write_text(text)
    app.build()
    elf=workspace/'hgb_pl_test/build/hgb_pl_test.elf'
    assert elf.is_file()
    files=sources+[xsa,hardware/'hgb_pl.bit',elf]
    (workspace/'manifest.json').write_text(json.dumps(dict(scope='候选PL及独立特征自检，非网页实时接入',files={p.relative_to(ROOT).as_posix():sha(p) for p in files}),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS HGB_PL_APP '+str(elf))
finally:vitis.dispose()
