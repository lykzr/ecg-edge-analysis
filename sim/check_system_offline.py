"""当前主体离线回归与干净目录复现；不安装、不训练、不操作板卡/Git。"""
import argparse,hashlib,importlib.metadata,json,os,platform,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODULES=['test_ecg_bridge.py','test_pc_bridge.py','test_pc_monitor.py','test_pc_serial.py','test_pc_capture.py',
         'test_runtime_link.py','test_system_edges.py','test_input_contract.py','test_int8_reference.py','test_checkout.py','test_ui_faults.py','test_rate500.py','test_pipeline500.py']
def run(output,clean):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    root=ROOT
    if clean:
        root=output/'checkout';root.mkdir()
        required=json.loads((ROOT/'sim/checkout_files.json').read_text(encoding='utf-8'))['required']
        for name in required:
            src=(ROOT/name).resolve();src.relative_to(ROOT)
            dst=root/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        assert not (root/'tmp').exists()
    rows=[]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    for i,args in enumerate([['sim/check_checkout.py'],['sim/check_qrs_runtime.py'],['sim/check_system_release.py']]+[['-m','unittest','discover','-s','sim','-p',m] for m in MODULES]):
        p=subprocess.run([sys.executable,'-B']+args,cwd=root,env=env,capture_output=True,timeout=240)
        (output/f'check_{i:02}.log').write_bytes(p.stdout+p.stderr)
        rows.append(dict(args=args,passed=p.returncode==0,returncode=p.returncode))
        if p.returncode:print((p.stdout+p.stderr).decode(errors='replace')[-2000:])
    dependencies={}
    for name in ('numpy','scipy','wfdb','pandas'):
        try:dependencies[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:dependencies[name]=None
    info=dict(passed=all(r['passed'] for r in rows),clean_copy=clean,checks=rows,python=sys.version,platform=platform.platform(),dependencies=dependencies,
        scope='source-only copy; uses existing external Python/GCC/Tk; no package install, full final hardware rebuild or board validation')
    (output/'summary.json').write_text(json.dumps(info,indent=2),encoding='utf-8');print(json.dumps(info));return 0 if info['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--clean-copy',action='store_true');a=p.parse_args();sys.exit(run(a.output,a.clean_copy))
