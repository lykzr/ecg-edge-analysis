"""授权后实板流式回放，检查结束前结果、逐拍计时及冻结整段对照。"""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'sim')]
import numpy as np
from ecg_cnn_stream import transfer_stream
from ecg_bridge_serial import DuplexSerial
from ecg_ports import enumerate_ports

def run(source,port,device_id,output,realtime=False):
    ports,_=enumerate_ports();assert sum(p['port']==port and p['device_id']==device_id for p in ports)==1
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(exist_ok=False)
    signal=np.loadtxt(source,delimiter=',');updates=[];start=time.perf_counter()
    def blocks():
        for i in range(0,len(signal),32):
            if realtime:time.sleep(max(0,start+min(i+32,len(signal))/500-time.perf_counter()))
            yield signal[i:i+32]
    def update(r):
        if r['events']:updates.append(dict(samples=r['samples'],events=len(r['events']),seconds=time.perf_counter()-start))
    serial=DuplexSerial(port)
    try:r=transfer_stream(blocks(),serial,output,'hp05',len(signal),on_update=update)
    finally:serial.close()
    assert any(u['samples']<len(signal) for u in updates),'结束前没有分类结果'
    from check_cnn_board import verify
    comparison=verify(output,source)
    result=dict(passed=True,realtime_paced=realtime,updates=updates,comparison=comparison,performance=r['performance'],
        max_algorithm_wait_ms=max(e['algorithm_wait_ms'] for e in r['events']),flash_written=False)
    (output/'stream_check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,events=len(r['events']),performance=r['performance'])))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','port','device-id','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--realtime',action='store_true');a=p.parse_args();run(a.source,a.port,a.device_id,a.output,a.realtime)
