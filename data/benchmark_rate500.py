"""500Hz适配候选对冻结360Hz逐记录配对回归；不读取分类独立测试。"""
import argparse,array,csv,json,subprocess,sys,time,hashlib
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'data'))
from ecg_dataset import load_record,metrics,BEAT_CODES,digest,aggregate

def run(raw,golden,exe,out,records=None,native=False):
 exe=exe.resolve()
 p=json.loads((ROOT/'data/qrs_runtime_protocol.json').read_text())
 for n,h in p['source_sha256'].items():
  if digest(ROOT/n)!=h:raise ValueError('冻结源变化：'+n)
 names=p['development_records']+p['evaluation_records']
 if records:names=records
 out.mkdir(parents=True,exist_ok=False)
 sources=[ROOT/'src/ps/ecg_rate500'/n for n in ('rate500.c','rate500.h','coefficients.h','pipeline500.c','window500.h')]+[ROOT/'sim/ecg_rate500_host.c',ROOT/'sim/ecg_pipeline500_host.c',ROOT/'data/benchmark_rate500.py',ROOT/'build/generate_rate500_runtime.py',ROOT/'src/ps/ecg_runtime/runtime.h',ROOT/'src/ps/ecg_runtime/pipeline.h',ROOT/'src/ps/ecg_classification/classification.c',ROOT/'src/ps/ecg_classification/classification.h']
 protocol=dict(scope='KNOWN_DATA_PAIRED_RATE_ADAPTATION',independent_test=False,native_500_capture=False,records=names,gate=p['gate'],rate='500 source; causal 18/25 FIR; frozen360 detector; source positions',baseline=str(golden),equivalence='No previously passing record may fail original gate; per-record FN/FP not above baseline; V matches not below baseline. Position/RR MAE may increase at most 2 ms for source-grid quantization. All startup/tail remain counted.',source_sha256={n.relative_to(ROOT).as_posix():digest(n) for n in sources},executable_sha256=digest(exe))
 if (exe.parent/'candidate.json').is_file():
  candidate=json.loads((exe.parent/'candidate.json').read_text(encoding='utf-8-sig'));protocol['rate']=candidate['rate'];q=ROOT/candidate['adapter_source'];protocol['source_sha256'][q.relative_to(ROOT).as_posix()]=digest(q)
  if 'runtime_source' in candidate:
   q=ROOT/candidate['runtime_source'];protocol['source_sha256'][q.relative_to(ROOT).as_posix()]=digest(q);protocol['candidate']=candidate
 protocol['baseline_scores_sha256']={n:digest(golden/n/'summary.json') for n in names}
 protocol['native_500_detector']=native
 if native:
  protocol['rate']='500Hz native detector; physical time windows; no resampling at runtime'
  for q in [ROOT/'build/generate_runtime500.py',exe.parent/'runtime500.c',exe.parent/'generation.json']:
   protocol['source_sha256'][q.relative_to(ROOT).as_posix()]=digest(q)
 (out/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8');rows=[]
 for rec in names:
  started=time.monotonic();xs,labels,meta=load_record(raw,rec,'MLII');base=json.loads((golden/rec/'summary.json').read_text())
  assert meta['source_sha256']==base['source_sha256']
  up=resample_poly(np.asarray(xs,dtype=float),25,18)
  source=np.clip(np.copysign(np.floor(np.abs(up)+.5),up),-32768,32767).astype('<i2')
  proc=subprocess.run([str(exe.resolve())],input=source.tobytes(),capture_output=True,timeout=120)
  (out/(rec+'_native.log')).write_bytes(proc.stderr)
  if proc.returncode:raise RuntimeError('候选执行失败：'+rec+str(proc.returncode))
  ev=[tuple(map(int,line.split(','))) for line in proc.stdout.decode().splitlines()]
  (out/(rec+'_events.csv')).write_bytes(proc.stdout)
  refs=[(i*25+9)//18 for i,c in labels if c in BEAT_CODES];codes=[c for i,c in labels if c in BEAT_CODES]
  score,pairs,missed,extra=metrics(refs,[e[1] for e in ev],75)
  for key in ('position_mae_ms','rr_mae_ms'):
   if score[key] is not None:score[key]*=360/500
  vc=Counter(codes);vm=Counter(codes[i] for i,j,d in pairs);v=vm[5]/vc[5] if vc[5] else None
  g=p['gate'];checks=dict(sensitivity=score['sensitivity']>=g['sensitivity'],positive_predictivity=score['positive_predictivity']>=g['positive_predictivity'],position_mae=score['position_mae_ms']<=g['position_mae_ms'],rr_mae=score['rr_mae_ms']<=g['rr_mae_ms'],v_recall=v is None or v>=g['v_recall'])
  eq=dict(no_new_gate_failure=not all(base['checks'].values()) or all(checks.values()),fn_not_worse=score['FN']<=base['FN'],fp_not_worse=score['FP']<=base['FP'],v_not_worse=vm[5]>=base['v_matched'],position_error=score['position_mae_ms']<=base['position_mae_ms']+2,rr_error=score['rr_mae_ms']<=base['rr_mae_ms']+2)
  row=dict(record=rec,**score,v_reference=vc[5],v_matched=vm[5],v_recall=v,checks=checks,provisional_gate='PASS' if all(checks.values()) else 'FAIL',equivalence=eq,equivalent=all(eq.values()),baseline={k:base[k] for k in ('TP','FN','FP','v_matched')},source_sha256=meta['source_sha256'],input_sha256=hashlib.sha256(source.tobytes()).hexdigest(),source_samples=len(source),seconds=time.monotonic()-started)
  rows.append(row);report=dict(protocol=protocol,completed=len(rows),complete=len(rows)==len(names),equivalent=all(r['equivalent'] for r in rows),rows=rows,aggregate=aggregate(rows),qualified=False,board_test=False)
  (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
  print(rec,{k:row[k] for k in ('TP','FN','FP','v_matched','equivalent')},flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('raw','golden','exe','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--records',nargs='+');p.add_argument('--native',action='store_true');a=p.parse_args();run(a.raw,a.golden,a.exe,a.out,a.records,a.native)
