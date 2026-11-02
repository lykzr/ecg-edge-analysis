"""核对H27源码、匹配硬件和USB身份后临时JTAG运行，不写Flash。"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_cnn import MODEL
from ecg_ports import enumerate_ports
from ecg_bridge_serial import DuplexSerial
def load(manifest,xsdb,cable,port,device_id,output):
    manifest=Path(manifest).resolve();manifest.relative_to(ROOT/'tmp');data=json.loads(manifest.read_text())
    if data.get('application')!='cnn_batch' or data.get('protocol') not in ('CNN-BATCH-1','CNN-PL-1','ECG-DUAL-1','ECG-DUAL-STREAM-1') or data['model']['model_sha256']!=MODEL:raise ValueError('不是匹配的H27应用')
    for name,row in data['files'].items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if p.stat().st_size!=row['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('镜像不匹配：'+name)
    for name,h in data['sources'].items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('源码变更：'+name)
    for key in ('elf','bit','init'):
        if data[key] not in data['files']:raise ValueError('缺少匹配镜像校验：'+key)
    ports,_=enumerate_ports()
    if len([p for p in ports if p['port']==port and p['device_id']==device_id])!=1:raise ValueError('USB身份不匹配')
    # 在复位前确认串口空闲，避免下载完成却无法收样。
    serial=DuplexSerial(port);serial.close()
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    command=[str(xsdb),str(ROOT/'board/hgb_handoff/load.tcl'),cable,*[str(ROOT/data[k]) for k in ('bit','init','elf')]]
    invocation='& '+' '.join("'"+v.replace("'","''")+"'" for v in command)+'; exit $LASTEXITCODE'
    q=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',invocation],capture_output=True,timeout=90,cwd=output)
    (output/'jtag.log').write_bytes(q.stdout+q.stderr)
    if q.returncode or b'PASS HGB_BATCH_JTAG_STARTED' not in q.stdout:raise RuntimeError('JTAG启动失败，见jtag.log')
    result=dict(started=True,execution_verified=False,flash_written=False,model_sha256=MODEL,manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),cable=cable,port=port,device_id=device_id,scope='temporary JTAG start; UART inference separately verified')
    (output/'identity.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','xsdb','cable','port','device-id','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();load(a.manifest,a.xsdb,a.cable,a.port,a.device_id,a.output)
