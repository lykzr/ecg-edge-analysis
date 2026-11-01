"""当前Git仓库离线回归；不安装、不训练、不操作板卡/Git。"""
import argparse,hashlib,importlib.metadata,json,os,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODULES=['test_ecg_bridge.py','test_pc_bridge.py','test_pc_monitor.py','test_pc_serial.py','test_pc_capture.py',
         'test_runtime_link.py','test_system_edges.py','test_input_contract.py','test_int8_reference.py','test_checkout.py','test_ui_faults.py','test_rate500.py','test_pipeline500.py','test_system_consistency.py','test_binary_licenses.py','test_runtime500_board.py','test_vendor500.py','test_qspi_release.py','test_repository.py','test_skills.py']
def run(output,release_artifacts_only=False):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    root=ROOT
    rows=[]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for i,args in enumerate([['sim/check_checkout.py'],['sim/check_qrs_runtime.py'],['sim/check_system_release.py']+(['--artifacts-only'] if release_artifacts_only else []),['sim/check_repository.py']]+[['-m','unittest','discover','-s','sim','-p',m] for m in MODULES]):
        p=subprocess.run([sys.executable,'-B']+args,cwd=root,env=env,capture_output=True,timeout=240)
        (output/f'check_{i:02}.log').write_bytes(p.stdout+p.stderr)
        rows.append(dict(args=args,passed=p.returncode==0,returncode=p.returncode))
        if p.returncode:print((p.stdout+p.stderr).decode(errors='replace')[-2000:])
    dependencies={}
    for name in ('numpy','scipy','wfdb','pandas'):
        try:dependencies[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:dependencies[name]=None
    release_check=json.loads((output/'check_02.log').read_text(encoding='utf-8')) if rows[2]['passed'] else None
    info=dict(release_artifacts_only=release_artifacts_only,current_release_rebuild_qualified=release_check['current_rebuild_qualified'] if release_check else None,release_source_drift=release_check['source_drift'] if release_check else [],passed=all(r['passed'] for r in rows),checks=rows,python=sys.version,platform=platform.platform(),dependencies=dependencies,
        scope='current repository; uses existing external Python/GCC/Tk; no package install, full final hardware rebuild or board validation')
    (output/'summary.json').write_text(json.dumps(info,indent=2),encoding='utf-8');print(json.dumps(info));return 0 if info['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--release-artifacts-only',action='store_true',help='显式分开已冻结发布完整性与当前开发源码；默认仍严格核对');a=p.parse_args();sys.exit(run(a.output,a.release_artifacts_only))
