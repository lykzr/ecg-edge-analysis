"""实际360Hz运行时错误出口：每例新JTAG会话，不写Flash。"""
import argparse,json,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_bridge_serial import DuplexSerial
from ecg_bridge_core import BridgeClient
from ecg_bridge_protocol import encode,ack
from ecg_monitor_core import Monitor
from ecg_ports import enumerate_ports,validate_port
from verify_classification import sha

def run(manifest,xsdb,cable,port,identity,output):
 m=json.loads(manifest.read_text());output.mkdir(parents=True,exist_ok=False);rows=[]
 for name,row in m['files'].items():
  p=ROOT/name
  if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('镜像身份不符')
 for name,value in m['sources'].items():
  if sha(ROOT/name)!=value:raise ValueError('源码身份不符')
 for mode,expected in [('crc','BAD_CRC'),('partial','PARTIAL_TIMEOUT'),('idle','INPUT_TIMEOUT')]:
  folder=output/mode;folder.mkdir();ports,_=enumerate_ports();device=validate_port(port,{'device_id':identity},ports);serial=DuplexSerial(port);raw=bytearray();row=dict(mode=mode,passed=False,uart=device)
  try:
   hw=ROOT/'releases/latest/smoke/hardware'
   with (folder/'jtag.log').open('xb') as log:
    p=subprocess.run([str(xsdb),str(ROOT/'board/classification_handoff/run.tcl'),cable,str(hw/'ecg_system_candidate.bit'),str(hw/'ps7_init.tcl'),str(ROOT/m['elf'])],stdout=log,stderr=subprocess.STDOUT,timeout=90)
   if p.returncode:raise RuntimeError('JTAG未完成')
   client=BridgeClient(serial,Monitor(),uuid.uuid4().hex,'REPLAY',profile='runtime360',timeout=10)
   start=time.monotonic()
   while time.monotonic()-start<12:
    client.pump()
    if client.started and client.waiting is None:break
    time.sleep(.001)
   else:raise TimeoutError('未确认初始化')
   line=encode('D,0,1,0')
   if mode=='crc':line=line[:-2]+(b'1' if line[-2:-1]!=b'1' else b'2')+b'\n'
   elif mode=='partial':line=b'D,0,'
   else:line=b''
   (folder/'injection.bin').write_bytes(line)
   while line:
    n=serial.write(line);line=line[n:]
    if not n:raise TimeoutError('注入发送停滞')
   begin=time.monotonic();buffer=bytearray()
   while time.monotonic()-begin<9:
    data=serial.read(4096);raw.extend(data);buffer.extend(data)
    while b'\n' in buffer:
     end=buffer.index(10)+1;line=bytes(buffer[:end]);del buffer[:end]
     if line.startswith((b'W,',b'E,')):raise ValueError('错误输入产生数据')
     if line.startswith(b'A,'):
      session,count,state,reason=ack(line)
      if (session,count,state,reason)!=(client.session,0,'ERROR',expected):raise ValueError('错误确认不符')
      row.update(passed=True,error_reason=reason,response_s=time.monotonic()-begin,accepted=0)
    if row['passed']:break
    time.sleep(.001)
   if not row['passed']:raise TimeoutError('未返回错误确认')
  except Exception as error:row['error']=type(error).__name__+': '+str(error)
  finally:
   serial.close();(folder/'uart.log').write_bytes(raw);(folder/'result.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
  print(json.dumps(row),flush=True)
 (output/'summary.json').write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),rows=rows,scope='physical USB_UART error exits; no wireless unplug test'),indent=2)+'\n')
 if not all(r['passed'] for r in rows):raise RuntimeError('故障验收失败，见证据')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('manifest','xsdb','output'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('cable','port','device-id'):p.add_argument('--'+n,required=True)
 a=p.parse_args();run(a.manifest,a.xsdb,a.cable,a.port,a.device_id,a.output)
