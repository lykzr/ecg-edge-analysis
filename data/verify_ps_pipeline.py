"""全部已知记录的C窗口/RR逐拍对照；使用自动检测黄金事件，不使用专家位置补拍。"""
import argparse,array,csv,json,subprocess,sys,hashlib
from collections import deque
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src/reference'),str(ROOT/'data')]
from ecg_dataset import load_record,digest
from ecg_beat_window import BeatWindow
from ecg_classifier import ModelSpec,prepare
DTYPE=np.dtype([(n,'<u4') for n in ('generation','id','position','rr','fs','ready','status')]+[('wave','<f4',(128,)),('features','<f4',(3,))])
def run(raw,golden,executable,output):
 output.mkdir(parents=True,exist_ok=False);protocol=json.loads((ROOT/'data/qrs_runtime_protocol.json').read_text())
 for n,h in protocol['source_sha256'].items():
  if digest(ROOT/n)!=h:raise ValueError('冻结源变化')
 fold=ROOT/'model/baseline/residual_verified/fold_0';norm=json.loads((fold/'normalization.json').read_text())
 spec=ModelSpec('dev-residual-f0',digest(fold/'best_weights.pt'),digest(ROOT/'model/protocols/cnn_git_v1_protocol.json'),digest(fold/'normalization.json'),tuple(norm['rr_mean']),tuple(norm['rr_std']),False,'development')
 rows=[]
 for rec in protocol['development_records']+protocol['evaluation_records']:
  xs,_,meta=load_record(raw,rec,'MLII');saved=json.loads((golden/rec/'summary.json').read_text())
  if meta['source_sha256']!=saved['source_sha256']:raise ValueError('源数据不匹配')
  with (golden/rec/'events.csv').open(newline='') as f:events=[tuple(int(r[k]) for k in ('emission_index','index','rr_samples')) for r in csv.DictReader(f)]
  args=[str(executable.resolve())]+[str(v) for v in (*spec.rr_mean,*spec.rr_std)]
  p=subprocess.run(args,input=array.array('h',xs).tobytes(),capture_output=True,timeout=90)
  if p.returncode or len(p.stdout)%DTYPE.itemsize:raise RuntimeError('C窗口程序失败')
  native=np.frombuffer(p.stdout,dtype=DTYPE)
  if len(native)!=len(events):raise ValueError('输出心拍数量不一致')
  history=deque(maxlen=401);valid=invalid=0;max_wave=max_rr=0.
  for eid,(emitted,pos,rr) in enumerate(events,1):
   if rr:history.append(rr)
   ready=emitted if pos<128 else max(emitted,pos+191);incomplete=pos<128 or ready>=len(xs)
   if ready>=len(xs):ready=len(xs)-1
   a=native[eid-1]
   if tuple(int(a[n]) for n in ('generation','id','position','rr','fs','ready'))!=(1,eid,pos,rr,360,ready):raise ValueError('时轴/编号不一致')
   status=4 if incomplete else (2 if not rr else 0)
   if int(a['status'])!=status:raise ValueError('有效状态不一致')
   if incomplete:invalid+=1;continue
   beat=BeatWindow(pos,ready,rr,360,128,tuple(xs[pos-128:pos+192]),tuple(history))
   ref=prepare(beat,'unit',eid,spec)
   error=float(np.max(np.abs(a['wave']-ref.waveform)));max_wave=max(max_wave,error)
   np.testing.assert_allclose(a['wave'],ref.waveform,atol=1e-6,rtol=1e-6)
   if ref.rr:
    error=float(np.max(np.abs(a['features']-ref.rr)));max_rr=max(max_rr,error)
    np.testing.assert_allclose(a['features'],ref.rr,atol=1e-6,rtol=1e-6)
   valid+=1
  row=dict(record=rec,passed=True,beats=len(events),waveforms=valid,incomplete=invalid,max_wave=max_wave,max_rr=max_rr,source_sha256=meta['source_sha256'],native_output_sha256=hashlib.sha256(p.stdout).hexdigest());rows.append(row)
  report=dict(passed=True,completed=len(rows),rows=rows,scope='all known automatic windows C host parity; no independent accuracy or full-record ARM claim',model_inference=False)
  (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(rec,valid,invalid,max_wave,max_rr,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('raw','golden','executable','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();run(a.raw,a.golden,a.executable,a.output)
