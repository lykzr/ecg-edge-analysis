"""核对ARM真实DDR转储与冻结参考；不是主机替代运行，不给患者准确率。"""
from pathlib import Path
import argparse,json,hashlib,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'model/inference'))
from ecg_model.pipeline import DT

RESULT=np.dtype([('beat_id','<u4'),('position','<u4'),('decision_at','<u4'),('status','<u4'),('history_count','<u4'),('class_id','<i4'),('features','<f4',(192,)),('probability','<f8',(3,))])
def verify(directory,fixture):
    directory=Path(directory).resolve();fixture=Path(fixture).resolve()
    summary=json.loads((fixture/'fixture.json').read_text())
    for name,h in summary['files'].items():assert hashlib.sha256((fixture/name).read_bytes()).hexdigest()==h,name
    status=np.fromfile(directory/'status.bin',dtype='<u4')
    assert len(status)==33 and list(status[:5])==[0x48474231,1,7,816,2070],status[:5]
    np.testing.assert_array_equal(status[5:12],summary['counts'])
    results=np.fromfile(directory/'results.bin',dtype=RESULT);assert len(results)==2070
    requests=np.fromfile(directory/'requests.bin',dtype=DT);assert len(requests)==146
    codes=np.fromfile(directory/'codes.bin',dtype='<i2').reshape(2,30000)
    from scipy.signal import lfilter
    signal=np.loadtxt(ROOT/'model/inference/examples/synthetic500.csv',delimiter=',')
    reports=[];offset=0
    for i,name in enumerate(summary['cases']):
        with np.load(fixture/f'{name}.npz',allow_pickle=False) as z:
            n=len(z['requests']);r=results[offset:offset+n];offset+=n
            for field in ('beat_id','position'):
                np.testing.assert_array_equal(r[field],z['requests'][field])
            for field,expected in [('decision_at',z['decision_at']),('status',z['requests']['input_status']),('history_count',z['history']),('class_id',z['class_id'])]:np.testing.assert_array_equal(r[field],expected)
            np.testing.assert_allclose(r['features'],z['features'],rtol=2e-6,atol=2e-6)
            np.testing.assert_allclose(r['probability'],z['probabilities'],rtol=1e-10,atol=1e-10,equal_nan=True)
            if i<2:
                actual=requests[i*73:(i+1)*73]
                for field in DT.names:
                    if field in ('waveform','rr'):np.testing.assert_allclose(actual[field],z['requests'][field],rtol=2e-6,atol=2e-6)
                    else:np.testing.assert_array_equal(actual[field],z['requests'][field])
                a=500/(500+2*np.pi*.5)
                y=lfilter([a,-a],[1,-a],signal,zi=[-a*signal[0]])[0] if i==0 else signal
                expected=np.clip(np.copysign(np.floor(abs(y*4096)+.5),y),-32768,32767).astype(np.int16)
                np.testing.assert_array_equal(codes[i],expected)
            valid=z['class_id']>=0
            reports.append(dict(name=name,events=n,valid=int(valid.sum()),features_max_abs=float(np.max(abs(r['features']-z['features']))),probability_max_abs=float(np.max(abs(r['probability'][valid]-z['probabilities'][valid]))),classes_equal=True,decisions_equal=True,record_compute_us=int(status[16+i])))
    uart=(directory/'uart.log').read_bytes()
    assert b'BEGIN HGB_ARM model=375cf45a' in uart and b'DONE HGB_ARM cases=7 events=2070' in uart,'缺真实串口首末标记'
    result=dict(passed=True,arm_executed=True,hardware_operated=True,flash_written=False,fits=0,cases=reports,input_compute_us=status[12:14].tolist(),prepare_compute_us=status[14:16].tolist(),scope='physical ARM controlled batch test; not continuous wireless, accuracy or PL acceleration',files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in directory.iterdir() if p.is_file() and p.name!='verification.json'})
    (directory/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--fixture',required=True);a=p.parse_args();print(json.dumps(verify(a.directory,a.fixture),ensure_ascii=False))
