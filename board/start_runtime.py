"""按匹配清单临时启动ARM运行时；不写Flash、不自动枚举选择板卡。"""
import argparse,subprocess,sys
from pathlib import Path
from runtime_artifacts import resolve_runtime_artifacts
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True)
 p.add_argument('--xsdb',type=Path,required=True);p.add_argument('--cable',required=True);p.add_argument('--rate',type=int,choices=(360,500),default=500)
 a=p.parse_args();m,f=resolve_runtime_artifacts(a.manifest,expected_rate=a.rate)
 args=[str(a.xsdb),str(ROOT/'board/classification_handoff/run.tcl'),a.cable,str(f['bit']),str(f['init']),str(f['elf'])]
 result=subprocess.run(args,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:return result.returncode
 print('ARM已临时启动，构建ID='+m['build_id']+'；请在客户端开始新会话。未写Flash。')
 return 0
if __name__=='__main__':sys.exit(main())
