"""实际C与H27冻结PyTorch逐拍比对；不训练、不操作设备。"""
import argparse,ctypes as ct,json,os,subprocess,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'model/inference'),str(ROOT/'build')]
from export_cnn_arm import export
from model.cnn_fourclass.network import load_model,logits,hand_features,rr_sequence,tensor,torch
from ecg_model.pipeline import _features,DT
from scipy.signal import lfilter

class Request(ct.Structure):
    _fields_=[(n,ct.c_uint32) for n in ('generation','beat_id','position','rr_samples','sampling_hz','ready_at','input_status')]+[('waveform',ct.c_float*128),('rr',ct.c_float*3)]
class Result(ct.Structure):
    _fields_=[(n,ct.c_uint32) for n in ('beat_id','position','ready_at','status','history_count')]+[('class_id',ct.c_int32),('logits',ct.c_float*4),('probability',ct.c_float*4)]
class Input(ct.Structure):
    _fields_=[('previous_input',ct.c_double),('previous_output',ct.c_double)]+[(n,ct.c_uint32) for n in ('clipped','started','highpass')]
P=ct.POINTER(ct.c_float)
def verify(output,cc,real_csv=None):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    info=export(output/'parameters');core=ROOT/'src/ps/ecg_hgb';cnn=ROOT/'src/ps/ecg_cnn';native=ROOT/'model/inference/native'
    sources=[cnn/'network.c',cnn/'features.c',cnn/'stream.c',core/'prepare.c',output/'parameters/cnn_weights.c']+[native/n for n in ('pipeline500.c','rate500.c','classification.c','runtime500_bridge.c')]
    commands=[];objects=[];env=dict(os.environ,TMP=str(output),TEMP=str(output))
    with (output/'compile.log').open('wb') as log:
        for i,p in enumerate(sources):
            obj=output/f'part{i}.o';objects.append(obj)
            cmd=[cc,'-std=c11','-O2','-ffp-contract=off','-fno-fast-math','-Wall','-Wextra','-Werror','-I'+str(core),'-I'+str(cnn),'-I'+str(native),'-I'+str(output/'parameters'),'-include',str(core/'frozen.h'),'-c',str(p),'-o',str(obj)]
            if p.parent==native:cmd+=['-Wno-error=misleading-indentation']
            commands.append(cmd);q=subprocess.run(cmd,capture_output=True,env=env,timeout=120);log.write(q.stdout+q.stderr)
            if q.returncode:raise RuntimeError(q.stderr.decode(errors='replace'))
        library=output/'cnn.dll';cmd=[cc,'-shared',*[str(p) for p in objects],'-lm','-o',str(library)];commands.append(cmd)
        q=subprocess.run(cmd,capture_output=True,env=env,timeout=120);log.write(q.stdout+q.stderr)
        if q.returncode:raise RuntimeError(q.stderr.decode(errors='replace'))
    lib=ct.CDLL(str(library));lib.cnn_forward.argtypes=[P]*5
    lib.cnn_record.argtypes=[ct.POINTER(Request),ct.c_uint,ct.POINTER(Result)]
    lib.ecg_hgb_input.argtypes=[ct.POINTER(Input),ct.POINTER(ct.c_double),ct.c_size_t,ct.c_int,ct.POINTER(ct.c_int16)]
    lib.ecg_hgb_workspace_size.argtypes=[ct.c_uint32];lib.ecg_hgb_workspace_size.restype=ct.c_size_t
    lib.ecg_hgb_prepare.argtypes=[ct.POINTER(ct.c_int16),ct.c_uint32,ct.POINTER(Request),ct.c_uint32,ct.c_void_p,ct.c_size_t,ct.POINTER(ct.c_uint32)]
    lib.cnn_input_stream_size.restype=ct.c_size_t
    lib.cnn_input_stream_init.argtypes=[ct.c_void_p]
    lib.cnn_input_stream_push.argtypes=[ct.c_void_p,ct.c_int16,ct.c_uint32,ct.POINTER(Request)]
    lib.cnn_input_stream_finish.argtypes=[ct.c_void_p,ct.POINTER(Request)]
    lib.cnn_history_init.argtypes=[ct.c_void_p]
    lib.cnn_history_push.argtypes=[ct.c_void_p,ct.POINTER(Request),ct.POINTER(Result)]
    assert ct.sizeof(Request)==DT.itemsize==552 and ct.sizeof(Result)==56
    net=load_model(0);torch.set_num_threads(4);reports=[]
    def forward(x,rr,hand,hist):
        arrays=[np.ascontiguousarray(v,np.float32) for v in (x,rr,hand,hist)];out=(ct.c_float*4)()
        assert lib.cnn_forward(*[a.ctypes.data_as(P) for a in arrays],out)==0
        return np.array(out)
    z=np.load(ROOT/'model/cnn_fourclass/assets/golden_0.npz');hand=hand_features(z['x'],z['rr'],z['background'],z['history_count'])
    actual=np.array([forward(*row) for row in zip(z['x'],z['rr'],hand,z['history_rr'])]);expected=z['logits']
    # 在运行前固定FP32重排容差；类别必须完全相同。
    np.testing.assert_allclose(actual,expected,atol=2e-4,rtol=2e-5);np.testing.assert_array_equal(actual.argmax(1),expected.argmax(1))
    reports.append(dict(name='golden_fold0',beats=len(actual),max_logit_error=float(np.max(np.abs(actual-expected)))))
    rng=np.random.default_rng(270);x=rng.normal(size=(100,128)).astype('f4');rr=rng.uniform(0,1,(100,3)).astype('f4');bg=rng.normal(size=x.shape).astype('f4');counts=rng.integers(0,9,100);hist=rng.uniform(0,1,(100,8)).astype('f4');h=hand_features(x,rr,bg,counts)
    expected=logits(net,x,rr,bg,counts,hist);actual=np.array([forward(*row) for row in zip(x,rr,h,hist)])
    np.testing.assert_allclose(actual,expected,atol=2e-4,rtol=2e-5);np.testing.assert_array_equal(actual.argmax(1),expected.argmax(1))
    reports.append(dict(name='random_inputs',beats=100,max_logit_error=float(np.max(np.abs(actual-expected)))))
    signals=[('synthetic500',np.loadtxt(ROOT/'model/inference/examples/synthetic500.csv',delimiter=','))]
    if real_csv:
        raw=np.genfromtxt(real_csv,delimiter=',',names=True,encoding='utf-8-sig');signals.append(('ads1292r',(raw['ecg_raw']-8388608)*2420/(6*8388608)))
    for name,mv in signals:
        mv=np.ascontiguousarray(mv,np.float64);a=500/(500+2*np.pi*.5);filtered=lfilter([a,-a],[1,-a],mv,zi=[-a*mv[0]])[0]
        codes=np.clip(np.copysign(np.floor(np.abs(filtered*4096)+.5),filtered),-32768,32767).astype('<i2');ref=_features(codes);n=len(ref['requests'])
        state=Input();got_codes=np.empty(len(mv),'<i2')
        for start in range(0,len(mv),137):
            sl=slice(start,start+137);assert lib.ecg_hgb_input(ct.byref(state),mv[sl].ctypes.data_as(ct.POINTER(ct.c_double)),len(mv[sl]),1,got_codes[sl].ctypes.data_as(ct.POINTER(ct.c_int16)))==0
        np.testing.assert_array_equal(got_codes,codes)
        need=lib.ecg_hgb_workspace_size(len(mv));work=(ct.c_double*((need+7)//8))();requests=(Request*480)();count=ct.c_uint32()
        assert lib.ecg_hgb_prepare(got_codes.ctypes.data_as(ct.POINTER(ct.c_int16)),len(mv),requests,480,work,need,ct.byref(count))==0 and count.value==n
        got=np.frombuffer(bytes(requests)[:n*552],DT);np.testing.assert_array_equal(got,ref['requests'])
        results=(Result*n)();assert lib.cnn_record(requests,n,results)==0
        state=(ct.c_double*((lib.cnn_input_stream_size()+7)//8))();assert lib.cnn_input_stream_init(state)==0
        emitted=[];batch=(Request*32)();arrival=[]
        for index,code in enumerate(got_codes):
            count=lib.cnn_input_stream_push(state,int(code),index,batch);assert count>=0,(index,count)
            for j in range(count):emitted.append(bytes(batch[j]));arrival.append(index)
        count=lib.cnn_input_stream_finish(state,batch);assert count>=0
        for j in range(count):emitted.append(bytes(batch[j]));arrival.append(len(got_codes)-1)
        online_requests=np.frombuffer(b''.join(emitted),DT)
        if b''.join(emitted)!=bytes(requests)[:n*552]:
            for k in DT.names:
                if not np.array_equal(online_requests[k],got[k]):print('stream mismatch',k,online_requests[k][:4],got[k][:4],flush=True)
        assert b''.join(emitted)==bytes(requests)[:n*552], '在线请求与冻结整段重切拍不一致'
        history_state=(ct.c_double*5000)();lib.cnn_history_init(history_state)
        for i in range(n):
            online=Result();assert lib.cnn_history_push(history_state,ct.byref(requests[i]),ct.byref(online))==0
            assert bytes(online)==bytes(results[i]), ('在线历史/分类与整段不同',i)
        assert all(at>=q.ready_at for at,q in zip(arrival,requests)), '结果产生时刻早于可用输入'
        # 拒绝跳号与重复结束；新会话显式重置后可重新开始。
        assert lib.cnn_input_stream_push(state,0,len(got_codes),batch)<0
        assert lib.cnn_input_stream_finish(state,batch)<0
        assert lib.cnn_input_stream_init(state)==0
        assert lib.cnn_input_stream_push(state,0,1,batch)<0
        assert lib.cnn_input_stream_push(state,0,0,batch)>=0
        valid=ref['valid'];history=rr_sequence(ref['positions500'],valid);expected=logits(net,ref['x'][valid],ref['rr'][valid],ref['background'][valid],ref['history_count'][valid],history[valid])
        actual=np.array([list(r.logits) for r in results])[valid]
        np.testing.assert_allclose(actual,expected,atol=2e-4,rtol=2e-5);np.testing.assert_array_equal(actual.argmax(1),expected.argmax(1))
        np.testing.assert_array_equal([r.history_count for r in results],ref['history_count'])
        for r in results:
            if r.status:assert r.class_id==-1 and np.isnan(list(r.probability)).all()
        np.savez(output/(name+'.npz'),input_mv=mv,requests=got,expected=expected,actual=actual)
        np.savetxt(output/(name+'_mv.csv'),mv,delimiter=',',fmt='%.17g')
        reports.append(dict(name=name,samples=len(mv),events=n,valid=int(valid.sum()),online_requests_bytes_exact=True,online_history_results_bytes_exact=True,sequence_and_reset_rejections=True,max_logit_error=float(np.max(np.abs(actual-expected))) if len(actual) else 0))
    invalid=ref['requests'].copy();invalid[0]['input_status']=0;assert lib.cnn_record((Request*n).from_buffer_copy(invalid.tobytes()),n,(Result*n)())<0
    result=dict(passed=True,hardware=False,training=False,precision='FP32',atol=2e-4,rtol=2e-5,classes_exact=True,model=info,tests=reports,commands=commands)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(reports))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--cc',required=True);p.add_argument('--real-csv');a=p.parse_args();verify(a.output,a.cc,a.real_csv)
