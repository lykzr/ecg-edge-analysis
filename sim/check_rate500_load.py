"""实际500Hz C协议的有界虚拟UART压力检查；不代表ARM耗时或物理串口实测。"""
import argparse, ctypes as ct, hashlib, json, math, os, shutil, subprocess, sys
from collections import deque
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'build')]
from generate_rate500_runtime import run as generate
from ecg_bridge_core import BridgeClient
from ecg_monitor_core import Monitor

READY=ct.CFUNCTYPE(ct.c_int,ct.c_void_p)
BYTE=ct.CFUNCTYPE(None,ct.c_void_p,ct.c_ubyte)
class Io(ct.Structure):
    _fields_=[('ctx',ct.c_void_p),('ready',READY),('byte',BYTE)]

def build(folder):
    generate(folder)
    cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
    if not cc:raise RuntimeError('需要已有GCC，不安装')
    target=folder/('load.dll' if os.name=='nt' else 'load.so')
    sources=[ROOT/'src/ps/ecg_rate500'/n for n in ('pipeline500.c','rate500.c')]+[folder/'runtime500_bridge.c',folder/'link500.c',ROOT/'src/ps/ecg_classification/classification.c',ROOT/'sim/ecg_runtime_link_host.c']
    args=[cc,'-shared','-std=c11','-O2','-ffp-contract=off']+([] if os.name=='nt' else ['-fPIC'])+['-I'+str(ROOT/'src/ps'/n) for n in ('ecg_classification','ecg_runtime','ecg_rate500')]+[str(p) for p in sources]+['-lm','-o',str(target)]
    p=subprocess.run(args,capture_output=True,env=dict(os.environ,TMP=str(folder),TEMP=str(folder)),timeout=90)
    (folder/'compile.log').write_bytes(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    lib=ct.CDLL(str(target))
    lib.ecg_link_size.restype=lib.ecg_pipeline_size.restype=ct.c_size_t
    lib.ecg_link_init.argtypes=[ct.c_void_p,Io,ct.c_void_p,ct.c_uint]
    lib.ecg_link_feed.argtypes=[ct.c_void_p,ct.c_ubyte,ct.c_uint64]
    lib.ecg_link_step.argtypes=[ct.c_void_p,ct.c_uint64]
    for n in ('peak','failed'):getattr(lib,'ecg_link_'+n).argtypes=[ct.c_void_p]
    lib.ecg_link_error.argtypes=[ct.c_void_p];lib.ecg_link_error.restype=ct.c_char_p
    return lib,{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}

class Wire:
    """两向115200/8N1、64字节板端TX FIFO；PC接收队列及读节拍可独立受限。"""
    def __init__(self,lib,trace=0,read_period_ms=1,rx_limit=4096,stall_tx=False):
        self.lib=lib;self.now=0.;self.ticks=0;self.rx=deque();self.tx=deque();self.upload=deque()
        self.read_period=read_period_ms;self.rx_limit=rx_limit;self.stall_tx=stall_tx
        self.up_credit=self.down_credit=0.;self.rx_peak=self.up_bytes=self.down_bytes=0
        self.state=ct.create_string_buffer(lib.ecg_link_size());self.pipeline=ct.create_string_buffer(lib.ecg_pipeline_size())
        self.callbacks=(READY(lambda _:not self.stall_tx and len(self.tx)<64),BYTE(lambda _,b:self.tx.append(b)))
        self.io=Io(None,*self.callbacks);lib.ecg_link_init(self.state,self.io,self.pipeline,trace)
    def advance(self):
        self.ticks+=1;self.now=self.ticks/1000.;self.up_credit=min(64.,self.up_credit+11.52);self.down_credit=min(64.,self.down_credit+11.52)
        while self.tx and self.down_credit>=1:
            if len(self.rx)>=self.rx_limit:raise OSError('SIM_RX_OVERRUN: 有界PC接收队列满')
            self.rx.append(self.tx.popleft());self.down_credit-=1;self.down_bytes+=1
        while self.upload and self.up_credit>=1:
            self.lib.ecg_link_feed(self.state,self.upload.popleft(),self.ticks*1000);self.up_credit-=1;self.up_bytes+=1
        self.lib.ecg_link_step(self.state,self.ticks*1000)
        self.rx_peak=max(self.rx_peak,len(self.rx))
    def read(self,n):
        self.advance()
        if self.ticks%self.read_period:return b''
        return bytes(self.rx.popleft() for _ in range(min(n,len(self.rx))))
    def write(self,data):
        size=min(len(data),256-len(self.upload));self.upload.extend(data[:size]);return size

def signal(seconds,bpm):
    period=30000/bpm
    return [int(20000*math.exp(-.5*(((i-period/2+period/2)%period-period/2)/5.)**2)-4000*math.exp(-.5*(((i-period/2-13+period/2)%period-period/2)/8.)**2)) for i in range(int(seconds*500))]

def case(lib,name,*,bpm=180,seconds=30,burst_ms=1,read_ms=1,rx_limit=4096,capacity=4096,trace=0,stall=False,expected_error=None):
    xs=signal(seconds,bpm);wire=Wire(lib,trace,read_ms,rx_limit,stall);monitor=Monitor(buffer_samples=4096)
    client=BridgeClient(wire,monitor,'load','REPLAY',profile='runtime500',clock=lambda:wire.now,capacity=capacity,timeout=10)
    origin=None;produced=0;error=None;latencies=[];seen=0
    try:
        for _ in range(int((seconds+25)*1000)):
            if client.started and client.waiting is None and origin is None:origin=wire.now
            if origin is not None and not client.eof:
                elapsed=max(0.,wire.now-origin)
                due=min(len(xs),int(math.floor(elapsed*1000/burst_ms)*burst_ms/2)+1)
                if due>produced:client.add(xs[produced:due]);produced=due
                if produced==len(xs):client.finish_source()
            client.pump()
            events=list(monitor.events)
            for e in events:
                if e.seq>seen:
                    latencies.append(wire.now-origin-e.pos/500);seen=e.seq
            if client.done:
                if client.lines:raise ValueError('结束后有USB残行')
                break
        if not client.done:raise TimeoutError('SIM_SESSION_BOUND')
    except (OSError,ValueError,TimeoutError,BufferError) as exc:error=type(exc).__name__+': '+str(exc)
    firmware=lib.ecg_link_error(wire.state)
    completed=client.done and error is None
    row=dict(name=name,bpm=bpm,seconds=seconds,trace=trace,burst_ms=burst_ms,read_ms=read_ms,rx_limit=rx_limit,capacity=capacity,completed=completed,error=error,firmware_error=firmware.decode() if firmware else None,
        confirmed=client.confirmed,echoed=client.echoed,produced=produced,events=monitor.counts['events'],tx_peak=lib.ecg_link_peak(wire.state),rx_peak=wire.rx_peak,queue_peak=client.peak,
        simulated_elapsed_s=wire.now,up_bytes=wire.up_bytes,down_bytes=wire.down_bytes,max_event_delivery_delay_s=max(latencies,default=None),timing_scope='virtual UART delivery plus causal algorithm/window wait; excludes ARM execution time',input_sha256=hashlib.sha256(bytes().join(int(x).to_bytes(2,'little',signed=True) for x in xs)).hexdigest())
    if expected_error:
        row['passed']=not completed and error is not None and expected_error in error
    else:
        row['passed']=completed and client.confirmed==len(xs) and client.echoed==len(xs) and monitor.counts['events']>0 and client.peak<=capacity and row['tx_peak']<=8192 and wire.rx_peak<=rx_limit
    row['event_pairs']=[(e.pos,e.rr) for e in monitor.events]
    return row

def run(output):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    lib,sources=build(output/'generated')
    configs=[('normal_120',dict(bpm=120)),('high_180',dict(bpm=180)),('high_240',dict(bpm=240)),
        ('burst_500ms',dict(bpm=240,burst_ms=500)),('slow_read_10ms',dict(bpm=240,read_ms=10)),
        ('slow_read_100ms',dict(bpm=240,read_ms=100,expected_error='队列已满')),
        ('slow_read_500ms',dict(bpm=240,read_ms=500,rx_limit=8192,expected_error='队列已满')),
        ('sustained_120s',dict(bpm=240,seconds=120)),
        ('slow_read_10ms_sustained',dict(bpm=240,read_ms=10,seconds=300,expected_error='队列已满')),
        ('source_queue_reject',dict(burst_ms=500,capacity=32,expected_error='队列已满')),
        ('receiver_overrun_reject',dict(read_ms=500,rx_limit=128,expected_error='SIM_RX_OVERRUN')),
        ('stalled_tx_reject',dict(stall=True,expected_error='初始化就绪超时')),
        ('debug_trace_240',dict(bpm=240,trace=1))]
    rows=[]
    for name,cfg in configs:
        row=case(lib,name,**cfg);rows.append(row);(output/(name+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in row.items() if k not in ('event_pairs',)},ensure_ascii=False),flush=True)
    baseline=rows[2]['event_pairs']
    for row in rows[3:5]:
        row['events_match_unstressed']=row['event_pairs']==baseline;row['passed'] &= row['events_match_unstressed']
    # 调试跟踪允许显式失败，不能作为正常带宽合格条件。
    debug=rows[-1];debug['diagnostic_only']=True
    info=dict(passed=all(r['passed'] for r in rows[:-1]),baud=115200,format='8N1',wire_bytes_per_second_per_direction=11520,dt_ms=1,board_test=False,scope='actual C with bounded virtual UART; no ARM throughput/physical USB/wireless claim',sources=sources,cases=rows)
    (output/'summary.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    return info['passed']

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args();sys.exit(0 if run(args.output) else 1)
