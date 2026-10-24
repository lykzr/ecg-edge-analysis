"""生成固定FIR时延补偿及1点位置不确定性复核候选；不改冻结360Hz源。"""
from pathlib import Path
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
def run(out):
 p=ROOT/'src/ps/ecg_runtime/runtime.c';s=p.read_text(encoding='utf-8-sig')
 expected=json.loads((p.parent/'provenance.json').read_text(encoding='utf-8'))['port_sha256']['runtime.c']
 if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('冻结360Hz C父本变化，停止派生')
 old='int low=s->ne==8&&energy<.5*em&&inside<2.*outside;'
 new='''int low=s->ne==8&&energy<.5*em&&inside<2.*outside;
 /* 复核相邻±1点，不声称定位误差上界；仍使用原2倍能量门槛及独立佐证。 */
 int corroborated=0;for(unsigned kk=0;kk<s->su;++kk){EcgRuntimeEvent *e=&s->secondary[(s->sh+kk)%32];if(abs((int)e->position-pos)<=10){corroborated=1;break;}}
 if(low&&corroborated&&width>.5*previous_width){for(int shift=-1;shift<=1;shift+=2){int aa=MAX(0,pos+shift-28),bb=MIN(s->n,pos+shift+28),cc=MAX(0,pos+shift-86),dd=MIN(s->n,pos+shift+86);double ii=0.,oo=0.;
  for(int j=aa;j<=bb;++j)ii+=s->variation[j%CAP];for(int j=cc;j<aa;++j)oo+=s->variation[j%CAP];for(int j=bb+1;j<=dd;++j)oo+=s->variation[j%CAP];
  if(ii/(bb-aa+1)>=2.*oo/MAX(1,dd-cc-bb+aa)){low=0;break;}}}'''
 assert s.count(old)==1;s=s.replace(old,new)
 old='(uint32_t)(s->n+72)';assert s.count(old)==1;s=s.replace(old,'(uint32_t)(s->n+5)')
 old='while(s->t+31<=s->n';assert s.count(old)==1;s=s.replace(old,'while(s->t+61<=s->n')
 s=s.replace('#include "runtime.h"','#include "'+(ROOT/'src/ps/ecg_runtime/runtime.h').as_posix()+'"')
 out.mkdir(parents=True,exist_ok=False);(out/'runtime500_bridge.c').write_text(s,encoding='utf-8')
 meta=dict(rate='500 source; 1001-tap 18/25 FIR; 20-sample FIR delay and probe phase budget; primary waits extra30 to obtain independent gradient corroboration; +/-1 weak-context rescue only with corroboration and width above half preceding accepted beat; original thresholds',adapter_source='src/ps/ecg_rate500/rate500.c',runtime_source=(out/'runtime500_bridge.c').resolve().relative_to(ROOT).as_posix(),parent_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 link=(ROOT/'src/ps/ecg_runtime/link.c').read_text(encoding='utf-8').replace('QRS26-ARM','QRS26-500-ARM').replace('ps-runtime-ready','ps-runtime500-ready').replace('ps-runtime-1','ps-runtime500-1').replace('360','500').replace('216000ULL','300000ULL')
 (out/'link500.c').write_text(link,encoding='utf-8')
 (out/'candidate.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
