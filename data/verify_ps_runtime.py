"""冻结360Hz的C移植完整已知记录核验；不调参，不访问独立分类患者。"""
import argparse,array,csv,json,subprocess,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data'))
from ecg_dataset import load_record,metrics,BEAT_CODES,digest

def run(raw,golden,executable,output):
 protocol=json.loads((ROOT/'data/qrs_runtime_protocol.json').read_text())
 for n,v in protocol['source_sha256'].items():
  if digest(ROOT/n)!=v:raise ValueError('冻结参考变化：'+n)
 output.mkdir(parents=True,exist_ok=False);rows=[]
 for rec in protocol['development_records']+protocol['evaluation_records']:
  start=time.monotonic();xs,labels,meta=load_record(raw,rec,'MLII')
  saved=json.loads((golden/rec/'summary.json').read_text())
  if meta['source_sha256']!=saved['source_sha256']:raise ValueError('源数据身份不符')
  p=subprocess.run([str(executable.resolve())],input=array.array('h',xs).tobytes(),capture_output=True,timeout=90)
  (output/(rec+'_native.log')).write_bytes(p.stderr)
  actual=[tuple(map(int,s.split(','))) for s in p.stdout.decode().splitlines()]
  with (golden/rec/'events.csv').open(newline='') as f:
   expected=[tuple(int(r[k]) for k in ('emission_index','index','rr_samples')) for r in csv.DictReader(f)]
  equal=p.returncode==0 and actual==expected
  refs=[i for i,c in labels if c in BEAT_CODES];score,_,_,_=metrics(refs,[e[1] for e in actual],54)
  diff=next((dict(event=i,reference=a,native=b) for i,(a,b) in enumerate(zip(expected,actual)) if a!=b),None)
  row=dict(record=rec,equal=equal,events=len(actual),reference_events=len(expected),first_difference=diff,score=score,source_sha256=meta['source_sha256'],golden_events_sha256=digest(golden/rec/'events.csv'),seconds=time.monotonic()-start)
  rows.append(row);(output/(rec+'_events.csv')).write_bytes(p.stdout)
  report=dict(passed=all(r['equal'] for r in rows),completed=len(rows),rows=rows,independent_test=False,scope='C host port parity; no board/500Hz/algorithm quality acceptance',executable_sha256=digest(executable))
  (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
  print(rec,equal,len(actual),diff,flush=True)
 if not all(r['equal'] for r in rows):raise RuntimeError('移植差异保留，不发布')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('raw','golden','executable','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();run(a.raw,a.golden,a.executable,a.output)
