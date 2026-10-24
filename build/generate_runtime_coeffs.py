"""使用现有SciPy复核360→144窗口滤波系数；不自动安装/修改正式头。"""
import argparse,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'model/prepare'))
from prepare_cnn_expanded import resampling_filter
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 values=resampling_filter(360,144)
 text='/* SciPy1.18.1 firwin(101,0.2,Kaiser5)，冻结360→144窗口；非500Hz转换。 */\nstatic const double ecg_resample360[101]={\n'+',\n'.join(format(float(x)*2,'.17g') for x in values)+'\n};\n'
 with a.output.open('x',encoding='utf-8') as f:f.write(text)
 print(hashlib.sha256(a.output.read_bytes()).hexdigest())
