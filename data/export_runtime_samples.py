"""导出冻结360Hz/4096单位的已知公开数据标准CSV，不接厂商500Hz数据。"""
import argparse,csv,json
from pathlib import Path
from ecg_dataset import load_record
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',type=Path,required=True);p.add_argument('--record',default='100');p.add_argument('--seconds',type=float,default=30);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 protocol=json.loads((ROOT/'data/qrs_runtime_protocol.json').read_text())
 if a.record not in protocol['development_records']+protocol['evaluation_records'] or not 0<a.seconds<=1800:raise ValueError('只允许已有已知记录/有界时长')
 xs,_,meta=load_record(a.raw,a.record,'MLII');xs=xs[:int(a.seconds*360)]
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x',newline='',encoding='utf-8') as f:
  w=csv.writer(f);w.writerow(['index','sample','fs','scale']);w.writerows((i,x,360,4096) for i,x in enumerate(xs))
 print(json.dumps(dict(samples=len(xs),source=meta,scope='known public data; not acquisition or accuracy acceptance')))
