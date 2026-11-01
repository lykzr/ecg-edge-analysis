"""核对构建与USB身份后临时下载独立HGB验收程序并保存真实UART/JTAG结果。"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_ports import enumerate_ports
from ecg_serial import WindowsSerial

def run(manifest,output,xsdb,nm,cable,port,device_id):
    manifest=Path(manifest).resolve();output=Path(output).resolve();output.relative_to(ROOT/'tmp')
    data=json.loads(manifest.read_text())
    assert data['model']['fold']==0 and data['model']['model_sha256']=='375cf45ac1f315ecc517a219cb03340727304db8e7738626ac4b4920a5af00f8'
    for name,row in data['files'].items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],name
    for name,h in data['sources'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    ports,warnings=enumerate_ports();match=[p for p in ports if p['port']==port and p['device_id']==device_id]
    if len(match)!=1:raise ValueError('串口USB身份不匹配')
    elf=ROOT/data['elf'];symbols={}
    raw=subprocess.check_output([str(nm),'-g',str(elf)],timeout=30,text=True)
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)==3 and parts[-1].startswith('hgb_board_'):symbols[parts[-1]]=int(parts[0],16)
    output.mkdir(parents=True,exist_ok=False)
    specs=[('status',33*4),('results',2070*816),('requests',146*552),('codes',2*30000*2)]
    (output/'dumps.txt').write_text(''.join(f'{name}.bin 0x{symbols["hgb_board_"+name]:x} {size//4}\n' for name,size in specs))
    hardware=ROOT/'releases/latest/smoke/hardware'
    command=[str(xsdb),str(ROOT/'board/hgb_handoff/run.tcl'),cable,str(hardware/'ecg_system_candidate.bit'),str(hardware/'ps7_init.tcl'),str(elf),hex(symbols['hgb_board_status']),str(output/'dumps.txt'),str(output)]
    receipt=dict(port=match[0],cable=cable,manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),symbols=symbols,command=command,flash_written=False)
    (output/'identity.json').write_text(json.dumps(receipt,indent=2)+'\n')
    env=dict(os.environ,TMP=str(output),TEMP=str(output))
    serial=WindowsSerial(port)
    try:
        with (output/'uart.log').open('wb') as uart,(output/'jtag.log').open('wb') as log:
            invocation='& '+' '.join("'"+part.replace("'","''")+"'" for part in command)+'; exit $LASTEXITCODE'
            process=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-Command',invocation],cwd=output,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+300
            while process.poll() is None:
                block=serial.read()
                if block:uart.write(block);uart.flush()
                if time.monotonic()>deadline:
                    process.terminate();raise TimeoutError('验收进程超时，保留现场')
                time.sleep(.01)
            for _ in range(30):
                block=serial.read()
                if block:uart.write(block)
                time.sleep(.01)
            if process.returncode:raise RuntimeError('JTAG验收失败，查看jtag.log')
    finally:serial.close()
    if b'PASS HGB_ARM_EXECUTED_AND_DUMPED' not in (output/'jtag.log').read_bytes():
        raise RuntimeError('XSDB没有完成标记；即使进程返回0也不能记通过')
    for name,size in specs:
        if not (output/(name+'.bin')).is_file() or (output/(name+'.bin')).stat().st_size!=size:
            raise RuntimeError('板端转储缺失或长度错误：'+name)
    print('HGB_ARM_CAPTURED '+str(output),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','output','xsdb','nm','cable','port','device-id'):p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.manifest,a.output,a.xsdb,a.nm,a.cable,a.port,a.device_id)
