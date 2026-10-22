"""候选PS实际C与PC中转离线闭环；AXI为整数参考，不冒充硬件运行。"""
import argparse
import csv
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'board'),str(ROOT/'sim'),str(ROOT/'src/reference'),str(ROOT/'src/pc')]
from build_ecg_auto import prepare_sources
from test_ecg_bridge import Node,Io
from ecg_auto import AutoDetector
from ecg_reference import Config
from ecg_bridge_core import BridgeClient
from ecg_monitor_core import Monitor


class SampleNode(Node):
    def write_reg(self,context,offset,value):
        super().write_reg(context,offset,value)
        if offset==0:
            # AXI写入间隔远超3个内部时钟；仅显式推进启动计算，不能推进样本号。
            while self.detector.bootstrap_phase:self.detector.tick(valid=False)


def check(output,csv_input):
    output.mkdir(parents=True,exist_ok=False)
    sources=output/'generated_ps'
    original_hashes=prepare_sources(sources)
    for name in ('main.c','bridge.h','bridge_time.h'):
        assert (sources/name).read_text()==(ROOT/'src/ps/ecg_bridge'/name).read_text(),name
    generated=(sources/'bridge.c').read_text()
    original=(ROOT/'src/ps/ecg_bridge/bridge.c').read_text()
    expected=original.replace('ps-bridge-1','ps-auto-1').replace('QRS-ORIG-60','QRS-AUTOPEAK-60')
    expected=expected.replace('if(!put(s,line)||!ack(s,"READY","NA"))',
        'if(!put(s,line)||!put(s,"L,I,WARMUP samples=1000 policy=no_events preserve_indices\\n")||!ack(s,"READY","NA"))')
    assert generated==expected,'PS changes exceed identity/warmup allowance'
    gcc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
    if not gcc:raise RuntimeError('需要已有GCC，不安装、不跳过')
    binary=output/('bridge.dll' if os.name=='nt' else 'bridge.so')
    args=[gcc,'-shared',*(['-fPIC'] if os.name!='nt' else []),'-std=c11','-O2','-Wall','-Wextra','-Werror',
          '-I',str(sources),str(sources/'bridge.c'),str(ROOT/'sim/ecg_bridge_host.c'),'-o',str(binary)]
    result=subprocess.run(args,capture_output=True,env=dict(os.environ,TEMP=str(output),TMP=str(output)))
    (output/'compile.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('候选PS主机编译失败')
    lib=ct.CDLL(str(binary));lib.ecg_bridge_size.restype=ct.c_size_t
    lib.ecg_bridge_init.argtypes=[ct.c_void_p,Io]
    lib.ecg_bridge_feed.argtypes=[ct.c_void_p,ct.c_ubyte,ct.c_uint64]
    lib.ecg_bridge_step.argtypes=[ct.c_void_p,ct.c_uint64]
    lib.ecg_bridge_field.argtypes=[ct.c_void_p,ct.c_uint];lib.ecg_bridge_field.restype=ct.c_uint32
    lib.ecg_bridge_error.argtypes=[ct.c_void_p];lib.ecg_bridge_error.restype=ct.c_char_p
    pulses=[0]*5003
    for i in range(100,5003,500):pulses[i]=100 if i//500%2==0 else -100
    values=[int(r['sample']) for r in csv.DictReader(csv_input.open())]
    cases={}
    for name,xs in [('low_pulses',pulses),('constant',[2048]*3503),('user_csv',values)]:
        node=SampleNode(lib);node.detector=AutoDetector(Config(sample_rate_hz=500));monitor=Monitor()
        client=BridgeClient(node,monitor,'offline-auto','REPLAY',clock=lambda:node.now/1e6)
        index=0
        for _ in range(600000):
            if not client.eof and len(client.queue)<256:
                batch=xs[index:index+32];client.add(batch);index+=len(batch)
                if index==len(xs):client.finish_source()
            client.pump()
            if client.done:break
        assert client.done,node.error()
        assert node.inputs==xs and client.confirmed==client.echoed==monitor.counts['samples']==len(xs)
        assert monitor.decoder.counts['invalid']==0 and monitor.counts['wave_gap']==monitor.counts['event_gap']==0
        assert monitor.header.detector=='QRS-AUTOPEAK-60'
        assert b'L,I,WARMUP samples=1000 policy=no_events preserve_indices\n' in node.output
        reference=AutoDetector(Config(sample_rate_hz=500));expected_events=[]
        for value in xs:
            state=reference.feed_sample(value)
            if state.qrs_valid:expected_events.append((state.qrs_sample_index,state.rr_interval_samples))
        assert [(e.pos,e.rr) for e in monitor.events]==expected_events
        assert node.pops==len(expected_events)
        (output/(name+'_upload.log')).write_bytes(node.upload)
        (output/(name+'_usb_rx.log')).write_bytes(node.output)
        cases[name]=dict(samples=len(xs),events=expected_events,confirmed=client.confirmed,echoed=client.echoed)
    report=dict(passed=True,scope='actual PS C / fake serial / reference AXI only, not board',
        original_ps_sha256=original_hashes,generated_ps_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.iterdir()},cases=cases)
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--csv-input',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(check(args.output.resolve(),args.csv_input.resolve())))
