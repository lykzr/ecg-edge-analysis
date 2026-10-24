"""厂商CSV→新500Hz ARM临时JTAG验收；可模拟34字节采集源，不能冒充无线。"""
import argparse,csv,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'board')]
from runtime_artifacts import resolve_runtime_artifacts
from ecg_ports import enumerate_ports,validate_port
from ecg_bridge_serial import DuplexSerial
from ecg_bridge_worker import BridgeWorker
from ecg_capture_core import VendorCsv

class SimulatedRadio:
    """原CSV偏移码重新编码34字节；按500Hz给出，不验证真实蓝牙。"""
    def __init__(self,path):self.csv=VendorCsv(path);self.started=None;self.count=0
    def read(self,n):
        if n<34:raise ValueError('模拟源一次读取须容纳完整厂商帧')
        if self.started is None:self.started=time.monotonic()
        data=bytearray(b'\xaa\xbb')
        for _ in range(4):
            row=self.csv.read()
            if row is None:raise EOFError('模拟ADC源意外提前结束')
            data.extend(row.resp_raw.to_bytes(4,'big'));data.extend(row.ecg_raw.to_bytes(4,'big'))
        time.sleep(max(0,self.count/500-(time.monotonic()-self.started)))
        self.count+=4
        return bytes(data)
    def close(self):self.csv.close()

def run(a):
    manifest,files=resolve_runtime_artifacts(a.manifest,expected_rate=500)
    out=a.output.resolve();out.relative_to(ROOT/'tmp');out.mkdir(parents=True,exist_ok=False)
    source=a.csv.resolve();source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    ports,_=enumerate_ports();device=validate_port(a.port,{'device_id':a.device_id},ports)
    if not a.device_id or not device['candidate']:raise ValueError('板卡串口身份不明确')
    count=0
    with source.open(encoding='utf-8-sig') as stream:
        for _ in csv.DictReader(stream):count+=1
    if count<1 or (a.simulate_radio and count%4):raise ValueError('空文件或34字节模拟需完整四点组')
    report=dict(passed=False,build_id=manifest['build_id'],source_sha256=source_hash,source_points=count,
                simulated_radio=a.simulate_radio,real_wireless=False,adc_calibrated=False,uart=device)
    worker=None
    try:
        with (out/'jtag.log').open('xb') as log:
            p=subprocess.run([str(a.xsdb),str(ROOT/'board/classification_handoff/run.tcl'),a.cable,str(files['bit']),str(files['init']),str(files['elf'])],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if p.returncode or 'ECG_CLASS_JTAG_STARTED' not in (out/'jtag.log').read_text(errors='replace'):raise RuntimeError('JTAG未完成')
        serial=DuplexSerial(a.port);startup=bytearray();start=time.monotonic()
        try:
            while time.monotonic()-start<12:
                startup.extend(serial.read(4096))
                if b'H,ECG-UART-1,ps-runtime500-ready,boot,UNKNOWN,QRS26-500-ARM,500,4096,0xD\n' in startup:break
                if len(startup)>65536:raise ValueError('启动原文超限')
                time.sleep(.001)
            else:raise TimeoutError('缺少500Hz就绪身份')
        finally:
            (out/'startup_uart.bin').write_bytes(startup);serial.close()
        worker=BridgeWorker('serial' if a.simulate_radio else 'csv','simulated-radio' if a.simulate_radio else source,
                            a.port,out/'transfer',profile='runtime500',zynq_device=device,
                            sample_limit=count if a.simulate_radio else None,
                            source_factory=lambda *args:SimulatedRadio(source))
        worker.start();worker.join(count/500+45)
        if worker.is_alive():worker.stop();worker.join(15);raise TimeoutError('中转未结束')
        info,capture,_,(_,events,h)=worker.snapshot()
        if info['error'] or info['reason']!='completed' or not info['done']:raise ValueError(str(info))
        if (info['confirmed'],info['echoed'],capture['total'])!=(count,count,count):raise ValueError('收发数量不一致')
        expected=json.loads(a.expected.read_text(encoding='utf-8'))
        if source_hash!=expected['source_sha256']:raise ValueError('参考与输入来源不同')
        actual=[[e.seq,e.pos,e.rr,e.cls] for e in events]
        if actual!=expected['events']:raise ValueError('板端事件与主机同源C不一致')
        normalized=out/'transfer/capture/normalized.csv'
        if hashlib.sha256(normalized.read_bytes()).hexdigest()!=expected['normalized_sha256']:raise ValueError('换算结果与主机参考不同')
        report.update(passed=True,events=len(events),capture=capture,transfer=info,source_header=h.source,
                      normalized_sha256=hashlib.sha256(normalized.read_bytes()).hexdigest(),scope='physical Zynq nominal/DC input digital replay; source is saved CSV or simulated 34-byte radio; no actual wireless')
    except Exception as exc:report.update(error=type(exc).__name__+': '+str(exc))
    finally:
        if worker is not None and worker.is_alive():worker.stop();worker.join(15)
        (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('transfer','capture','uart')},ensure_ascii=False))
    return 0 if report['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('manifest','csv','expected','xsdb','output'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('port','device-id','cable'):p.add_argument('--'+n,required=True)
    p.add_argument('--simulate-radio',action='store_true');sys.exit(run(p.parse_args()))
