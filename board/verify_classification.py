"""显式授权后使用：核匹配镜像/源SHA与USB身份，开串口后临时JTAG自检；不写Flash。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_ports import enumerate_ports,validate_port
from ecg_serial import WindowsSerial
CHECKS=('RR_FLOAT32_CLIP','BOUNDED_QUEUE_BUSY','IDENTITY_COMPLETE','TIMEOUT_LATE_REJECT',
        'FIRST_RR_UNKNOWN','RESET_STALE_REJECT','INVALID_DUPLICATE_SINGLE_FLIGHT')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inside(name):
 p=(ROOT/name).resolve();p.relative_to(ROOT)
 if not p.is_file():raise FileNotFoundError(p)
 return p
def run(manifest,tool,cable,port,identity,output):
 manifest=manifest.resolve();manifest.relative_to(ROOT/'tmp')
 m=json.loads(manifest.read_text(encoding='utf-8'))
 if m['scope']!='ARM tensor queue only; no QRS/CNN/Flash':raise ValueError('用途不符')
 for name,row in m['files'].items():
  p=inside(name)
  if sha(p)!=row['sha256'] or p.stat().st_size!=row['bytes']:raise ValueError('镜像不符：'+name)
 for name,value in m['sources'].items():
  if sha(inside(name))!=value:raise ValueError('当前源码与ELF构建不符')
 ports,warnings=enumerate_ports();device=validate_port(port,dict(device_id=identity),ports)
 if not identity or not device['candidate']:raise ValueError('需要明确候选USB身份')
 output.mkdir(parents=True,exist_ok=False)
 (output/'plan.json').write_text(json.dumps(dict(manifest=m,cable=cable,uart=device,warnings=warnings,
  deadline_s=120,baud=115200,scope=m['scope']),indent=2)+'\n',encoding='utf-8')
 serial=None;proc=None;data=bytearray();report=dict(passed=False,scope=m['scope'],build_id=m['build_id'])
 try:
  serial=WindowsSerial(port,115200)
  hw=ROOT/'releases/latest/smoke/hardware'
  command=[str(tool),str(ROOT/'board/classification_handoff/run.tcl'),cable,str(hw/'ecg_system_candidate.bit'),str(hw/'ps7_init.tcl'),str(inside(m['elf']))]
  with (output/'jtag.log').open('xb') as log:
   proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   start=time.monotonic()
   while time.monotonic()-start<120:
    piece=serial.read(4096)
    if piece:
     data.extend(piece)
     with (output/'uart.log').open('ab') as f:f.write(piece)
     if len(data)>65536:raise OverflowError('串口记录超过64KiB')
    text=data.decode('ascii',errors='replace')
    end='PASS ECG_CLASS_INTERFACE failures=0 build='+m['build_id']+'\r\n'
    if end in text and proc.poll() is not None:break
    if b'FAIL ' in data:raise RuntimeError('实板输出FAIL，保留日志')
    if proc.poll() is not None and proc.returncode:raise RuntimeError('XSDB错误，保留日志')
    time.sleep(.01)
   else:raise TimeoutError('120秒未得到本次构建完整PASS')
  lines=text.splitlines()
  required=['BEGIN ECG_CLASS_INTERFACE build='+m['build_id'],
            'SCOPE ARM_TENSOR_QUEUE_ONLY NO_QRS NO_CNN NO_FLASH']+['PASS '+n for n in CHECKS]
  if any(lines.count(n)!=1 for n in required):raise ValueError('缺少/重复检查行')
  if 'ECG_CLASS_JTAG_STARTED' not in (output/'jtag.log').read_text(errors='replace'):raise ValueError('JTAG启动标记缺失')
  report.update(passed=True,checks=len(CHECKS),uart_bytes=len(data),uart_sha256=sha(output/'uart.log'),manifest_sha256=sha(manifest))
 except Exception as error:
  report['error']=type(error).__name__+': '+str(error)
 finally:
  if serial is not None:serial.close()
  if proc is not None and proc.poll() is None:proc.terminate();proc.wait(timeout=10)
  (output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report))
 if not report['passed']:raise RuntimeError('实板接口未通过，见记录')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('manifest','xsdb','output'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('cable','port','device-id'):p.add_argument('--'+n,required=True)
 a=p.parse_args();run(a.manifest,a.xsdb,a.cable,a.port,a.device_id,a.output)
