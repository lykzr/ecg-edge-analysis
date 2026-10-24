"""500Hz完整记录C窗口/RR与现有模型预处理逐拍对照，不训练/推理。"""
import argparse,json,subprocess,sys,hashlib,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'data'),str(ROOT/'model/prepare')]
from ecg_dataset import load_record,digest
from prepare_cnn_expanded import common_window,causal_rr
DT=np.dtype([('generation','<u4'),('beat_id','<u4'),('position','<u4'),('rr_samples','<u4'),('sampling_hz','<u4'),('ready_at','<u4'),('input_status','<u4'),('waveform','<f4',(128,)),('rr','<f4',(3,))])
def run(raw,exe,out):
 out.mkdir(parents=True,exist_ok=False);p=json.loads((ROOT/'data/qrs_runtime_protocol.json').read_text());cfg=json.loads((ROOT/'model/protocols/cnn_git_v1_protocol.json').read_text())['window'];rows=[]
 from scipy.signal import resample_poly
 for rec in p['development_records']+p['evaluation_records']:
  start=time.monotonic();xs,_,meta=load_record(raw,rec,'MLII');up=resample_poly(np.asarray(xs,float),25,18);xs=np.clip(np.copysign(np.floor(abs(up)+.5),up),-32768,32767).astype('<i2');signal=xs.astype(float)/4096.
  q=subprocess.run([str(exe.resolve()),'requests'],input=xs.tobytes(),capture_output=True,timeout=120);(out/(rec+'_native.log')).write_bytes(q.stderr)
  if q.returncode or len(q.stdout)%DT.itemsize:raise RuntimeError('C执行或结构大小错误')
  requests=np.frombuffer(q.stdout,dtype=DT);history=[];last=None;max_wave=max_rr=0.;incomplete=valid=0
  for r in requests:
   pos,rr,ready,status=map(int,(r['position'],r['rr_samples'],r['ready_at'],r['input_status']))
   if r['sampling_hz']!=500 or pos>ready or rr!=(0 if last is None else pos-last):raise ValueError('源位置/RR/时轴不符')
   last=pos
   if rr:history.append(rr)
   if status==4:
    if pos>=178 and pos+267<=len(xs):raise ValueError('错误地作废完整窗口')
    incomplete+=1;continue
   expected=common_window(signal,pos,500,cfg)
   if expected is None:raise ValueError('C提供了不完整波形')
   np.testing.assert_allclose(r['waveform'],expected,atol=1e-6,rtol=1e-6);max_wave=max(max_wave,float(abs(r['waveform']-expected).max()))
   if rr:
    np.testing.assert_allclose(r['rr'],causal_rr(history[-401:]),atol=1e-6,rtol=1e-6);max_rr=max(max_rr,float(abs(r['rr']-causal_rr(history[-401:])).max()))
   elif status!=2:raise ValueError('首RR未知未标记')
   valid+=1
  row=dict(record=rec,events=len(requests),complete_windows=valid,incomplete=incomplete,max_wave_error=max_wave,max_rr_error=max_rr,source_sha256=meta['source_sha256'],seconds=time.monotonic()-start);rows.append(row)
  result=dict(passed=True,completed=len(rows),complete=len(rows)==42,rows=rows,executable_sha256=digest(exe),scope='known500 synthesized source; C windows/RR parity only; no final CNN/board/real AFE');(out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(rec,valid,max_wave,max_rr,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('raw','exe','out'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();run(a.raw,a.exe,a.out)
