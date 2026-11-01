"""按明确清单生成本地提交副本，验证后才报告成功；不操作Git或板卡。"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def package(output):
 output=Path(output).resolve();output.relative_to(ROOT/'tmp')
 if output.exists():raise FileExistsError('目标已存在，禁止覆盖：'+str(output))
 names=json.loads((ROOT/'sim/submission_files.json').read_text(encoding='utf-8'))['files']
 entries=[]
 for name in names:
  p=(ROOT/name).resolve();p.relative_to(ROOT)
  if not p.is_file():raise FileNotFoundError(name)
  entries.append((name,p,digest(p)))
 output.mkdir(parents=True)
 for name,p,h in entries:
  target=output/name;target.resolve().relative_to(output);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
  if digest(target)!=h:raise ValueError('复制校验失败：'+name)
 checks=[]
 for command in [['sim/check_checkout.py'],['sim/check_system_release.py']]:
  result=subprocess.run([sys.executable,'-B']+command,cwd=output,capture_output=True,text=True,encoding='utf-8',errors='replace')
  checks.append(dict(command=command,passed=result.returncode==0,output=result.stdout+result.stderr))
 receipt=dict(passed=all(c['passed'] for c in checks),files={n:h for n,p,h in entries},checks=checks,scope='本地审阅副本；未安装、构建、连板或公开发布')
 output.with_suffix('.receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
 if not receipt['passed']:raise RuntimeError('副本检查失败，保留目录与收据供排查')
 print(json.dumps(dict(passed=True,files=len(entries),output=str(output)),ensure_ascii=False))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);package(parser.parse_args().output)
