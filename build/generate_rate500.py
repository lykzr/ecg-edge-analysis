"""生成500→360Hz独立有理FIR系数；保留冻结QRS，不覆盖历史转换器。"""
from pathlib import Path
import argparse,json,hashlib
from scipy.signal import firwin
ROOT=Path(__file__).resolve().parents[1]
def run(output):
 p=Path(output);h=firwin(1001,1/25,window=('kaiser',8.6))*18
 text='/* 自编系数表：firwin(1001,1/25,Kaiser8.6)*18；18/25有理FIR，群延迟20个360Hz点。 */\nstatic const double ecg_rate500_fir[1001]={\n'+',\n'.join(format(float(v),'.17g') for v in h)+'\n};\n'
 p.write_text(text,encoding='utf-8');print(hashlib.sha256(p.read_bytes()).hexdigest())
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
