"""生成当前裸机BSP/FSBL的源码许可证据，未知项保留，不作法律结论。"""
import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(workspace,output):
 workspace=Path(workspace).resolve();workspace.relative_to(ROOT/'tmp')
 output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
 rows=[];copyrights=set();compiled=set()
 for command_file in workspace.rglob('compile_commands.json'):
  for row in json.loads(command_file.read_text(encoding='utf-8')):
   src=Path(row['file'])
   if not src.is_absolute():src=Path(row['directory'])/src
   compiled.add(src.resolve())
 for p in sorted(workspace.rglob('*')):
  if not p.is_file() or p.suffix.lower() not in ('.c','.h','.s','.ld','.cmake'):continue
  data=p.read_bytes();text=data.decode('utf-8',errors='replace')
  tags=sorted(set(t.strip() for t in re.findall(r'SPDX-License-Identifier:\s*([^\r\n*]+)',text)))
  if not tags and 'GNU General Public License' in text[:5000]:tags=['GPL-header; inspect version in source']
  notices=[x.strip(' /*') for x in text.splitlines()[:100] if 'Copyright' in x or 'copyright' in x]
  copyrights.update(notices)
  status='spdx_declared' if tags else ('permission_header' if 'Permission is hereby granted, free of charge' in text[:10000] else 'unresolved')
  rows.append(dict(path=p.relative_to(workspace).as_posix(),sha256=hashlib.sha256(data).hexdigest(),spdx=tags,status=status,copyright=notices,listed_compile_input=p.resolve() in compiled))
 if not rows:raise ValueError('未找到BSP/FSBL源码，不能当检查通过')
 if not any(x['listed_compile_input'] for x in rows):raise ValueError('没有匹配实际编译输入，不能当编译许可检查通过')
 result=dict(source_files=len(rows),listed_compile_sources=sum(x['listed_compile_input'] for x in rows),compiled_unresolved=[x['path'] for x in rows if x['listed_compile_input'] and x['status']=='unresolved'],compiled_gpl=[x['path'] for x in rows if x['listed_compile_input'] and any('GPL' in t for t in x['spdx'])],statuses=dict(collections.Counter(x['status'] for x in rows)),files=rows,scope='source/header inventory only; unresolved/generated/tool IP and binary link provenance not legal clearance')
 (output/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (output/'copyrights.txt').write_text('\n'.join(sorted(copyrights))+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in result.items() if k!='files'}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.workspace,a.output)
