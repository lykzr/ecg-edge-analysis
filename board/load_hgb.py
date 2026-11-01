"""核对独立HGB批处理应用清单、USB身份后临时JTAG运行；不写Flash。"""
from pathlib import Path
import argparse,hashlib,json,subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_ports import enumerate_ports

def load(manifest,xsdb,cable,port,device_id,output):
    manifest=Path(manifest).resolve();data=json.loads(manifest.read_text())
    if data.get('application')!='batch':raise ValueError('不是独立HGB收样应用')
    for name,row in data['files'].items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if p.stat().st_size!=row['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('镜像不匹配：'+name)
    for name,h in data['sources'].items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('源码变更：'+name)
    ports,_=enumerate_ports()
    if len([v for v in ports if v['port']==port and v['device_id']==device_id])!=1:raise ValueError('USB身份不匹配')
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    hardware=ROOT/'releases/latest/smoke/hardware'
    command=[str(xsdb),str(ROOT/'board/hgb_handoff/load.tcl'),cable,str(hardware/'ecg_system_candidate.bit'),str(hardware/'ps7_init.tcl'),str(ROOT/data['elf'])]
    invocation='& '+' '.join("'"+v.replace("'","''")+"'" for v in command)+'; exit $LASTEXITCODE'
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',invocation],capture_output=True,timeout=90,cwd=output)
    (output/'jtag.log').write_bytes(result.stdout+result.stderr)
    if result.returncode or b'PASS HGB_BATCH_JTAG_STARTED' not in result.stdout:raise RuntimeError('下载未完成，查看jtag.log')
    receipt=dict(passed=True,port=port,device_id=device_id,cable=cable,manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),elf_sha256=hashlib.sha256((ROOT/data['elf']).read_bytes()).hexdigest(),flash_written=False,scope='temporary JTAG start; results separately verified')
    (output/'identity.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('manifest','xsdb','cable','port','device-id','output'):p.add_argument('--'+n,required=True)
    a=p.parse_args();load(a.manifest,a.xsdb,a.cable,a.port,a.device_id,a.output)
