"""从冻结360Hz C生成独立500Hz物理参数候选；不覆盖冻结源。"""
import argparse,re,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# 只在指定函数内换算样本时间/数组尺寸；比例阈值、决策流程和队列容量保留。
MAPPING={
'coeff':{'360.':'500.'},
'aligned':{'57':'81','58':'82'},
'annotation':{'54':'75','36':'50','28':'40','29':'41','86':'120','144':'200','57':'81','100':'128'},
'peaktype':{'86':'120'},
'smooth':{'6':'8','5':'7','7':'9'},
'qfilter':{'24':'32','6':'8','12':'16','18':'24','2304.':'4096.'},
'primary_step':{'24':'32','18':'25','118':'165','86':'120','72':'100','7':'10','12':'16','90':'125','864':'1200'},
'secondary_confirm':{'360':'500','180':'250','54':'75','86':'120'},
'secondary_push':{'37':'51','19':'26','271':'375','135':'187','360':'500'},
'ecg_runtime_init':{'24':'32','72':'100','288':'400','94':'131','18':'25','135':'187'},
'ecg_runtime_push':{'31':'41','1440':'2000','54':'75','28':'40','29':'41'}
}
def generate(output):
 p=ROOT/'src/ps/ecg_runtime/runtime.c';s=p.read_text(encoding='utf-8-sig');original=hashlib.sha256(p.read_bytes()).hexdigest()
 # 每个函数体以顶层换行右括号/下一函数定义定位，禁止全文件裸数字替换。
 names=list(MAPPING)
 markers=list(re.finditer(r'^(?:static )?(?:int64_t|size_t|void|int|double|Biquad) (\w+)\(',s,re.M))
 pieces=[];last=0;changes={}
 for i,m in enumerate(markers):
  end=markers[i+1].start() if i+1<len(markers) else len(s);name=m.group(1);block=s[m.start():end]
  pieces.append(s[last:m.start()]);table=MAPPING.get(name,{})
  if table:
   found={};pat=r'(?<![\w.])(?:'+ '|'.join(re.escape(k) for k in sorted(table,key=len,reverse=True))+r')(?![\w.])'
   def sub(x):found[x.group()]=found.get(x.group(),0)+1;return table[x.group()]
   block=re.sub(pat,sub,block);changes[name]=found
   if not found:raise ValueError('未识别函数参数：'+name)
  pieces.append(block);last=end
 pieces.append(s[last:]);out=''.join(pieces)
 out=out.replace('templates[8][57]','templates[8][81]').replace('gwindow[37]','gwindow[51]').replace('bwindow[271]','bwindow[375]')
 out=out.replace('#include "runtime.h"','#include "'+(ROOT/'src/ps/ecg_runtime/runtime.h').as_posix()+'"')
 out='/* 独立500Hz派生候选；固定时间参数换算，未经验证不得发布。 */\n'+out
 output.mkdir(parents=True,exist_ok=False);(output/'runtime500.c').write_text(out,encoding='utf-8')
 (output/'generation.json').write_text(json.dumps(dict(parent_sha256=original,changes=changes,source_sha256=hashlib.sha256(out.encode()).hexdigest()),indent=2),encoding='utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();generate(a.output)
