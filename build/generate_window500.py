"""生成源500Hz窗口→144Hz模型输入的固定系数，不改模型协议。"""
from pathlib import Path
import argparse
from scipy.signal import firwin
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();h=firwin(2501,1/125,window=('kaiser',5.))*36
 a.output.write_text('/* 源500Hz窗口，36/125多相FIR；Kaiser5，与现有common_window一致。 */\nstatic const double ecg_window500_fir[2501]={\n'+',\n'.join(format(float(x),'.17g') for x in h)+'\n};\n',encoding='utf-8')
