"""应用/FSBL实际链接组成与许可来源证据；不作最终分发许可结论。"""
import argparse,collections,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def compiled_sources(workspace):
    by_name=collections.defaultdict(dict)
    for command_file in workspace.rglob('compile_commands.json'):
        for row in json.loads(command_file.read_text(encoding='utf-8')):
            source=Path(row['file'])
            if not source.is_absolute():source=Path(row['directory'])/source
            if not source.is_file():continue
            digest=sha(source)
            if digest in by_name[source.name]:continue
            text=source.read_text(encoding='utf-8',errors='replace')
            header='\n'.join(text.splitlines()[:150])
            tags=sorted(set(re.findall(r'SPDX-License-Identifier:\s*([^\r\n*]+)',header)))
            label=('spdx' if tags else 'Eric Young notice' if 'Eric Young' in header else
                   'Cygnus permission' if 'Cygnus' in header and 'Permission' in header else
                   'permission header' if 'Permission is hereby granted' in header else 'generated_or_unresolved')
            by_name[source.name][digest]=dict(path=str(source.resolve()),sha256=digest,spdx=tags,license_evidence=label,
                copyright=[line.strip(' /*') for line in header.splitlines() if 'Copyright' in line or 'copyright' in line])
    return by_name

def inspect_map(path):
    text=path.read_text(encoding='utf-8',errors='replace')
    # 第一段是按未定义符号提取的archive成员；后文可能重复或包含被丢弃section。
    header=re.split(r'Allocating common symbols|Discarded input sections|Memory Configuration',text,maxsplit=1)[0]
    selected=collections.defaultdict(set)
    for archive,member in re.findall(r'^(\S.*?\.a)\(([^)]+)\)',header,re.M):
        selected[str(Path(archive.replace('\\','/')).resolve())].add(member)
    loaded=[]
    for name in re.findall(r'^LOAD (.+)$',text,re.M):
        if name.endswith('.a'):loaded.append(str(Path(name.replace('\\','/')).resolve()))
    rows=[]
    for name in sorted(set(loaded)|set(selected)):
        p=Path(name)
        if not p.is_file():raise FileNotFoundError('实际链接库缺失：'+name)
        family=('GCC runtime; upstream GPL-3.0-or-later with GCC-exception-3.1; vendor build provenance pending' if p.name=='libgcc.a' else
                'Newlib multifile notices; see actual toolchain header version; vendor patch correspondence pending' if p.name in ('libc.a','libm.a','libg.a') else
                'BSP source notices and generated-source provenance')
        rows.append(dict(path=name,bytes=p.stat().st_size,sha256=sha(p),selected_members=sorted(selected[name]),selected_count=len(selected[name]),loaded=name in loaded,license_scope=family))
    return rows

def run(root,manifest,tool_bin,output):
    root=Path(root).resolve();output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    data=json.loads(Path(manifest).read_text(encoding='utf-8'))
    files={}
    for name,row in data['files'].items():
        p=(root/name).resolve();p.relative_to(root)
        if p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('构建证据不符：'+name)
        files[name]=p
    roles={}
    for role,basename in [('app_map','ecg_runtime.map'),('fsbl_map','fsbl.map'),('fsbl','fsbl.elf')]:
        found=[p for p in files.values() if p.name==basename]
        if len(found)!=1:raise ValueError('需要独立且唯一的'+basename)
        roles[role]=found[0]
    roles['app']=files[data['elf']]
    tool_bin=Path(tool_bin);tools={}
    compiler=tool_bin/'arm-none-eabi-gcc.exe'
    version=subprocess.run([str(compiler),'--version'],capture_output=True,text=True,check=True).stdout
    tools['compiler']=dict(path=str(compiler),sha256=sha(compiler),version=version)
    newlib_header=tool_bin.parent/'aarch32-xilinx-eabi/usr/include/_newlib_version.h'
    if not newlib_header.is_file():raise FileNotFoundError('缺少实际Newlib版本头，不能猜测版本')
    newlib_text=newlib_header.read_text(encoding='utf-8')
    newlib_version=re.search(r'#define\s+_NEWLIB_VERSION\s+"([^"]+)"',newlib_text)
    if not newlib_version:raise ValueError('无法识别Newlib版本')
    tools['newlib']=dict(header=str(newlib_header),sha256=sha(newlib_header),version=newlib_version.group(1))
    source_index=compiled_sources(Path(manifest).resolve().parent)
    reports={}
    for role in ('app','fsbl'):
        elf=roles[role];mapfile=roles[role+'_map'];nm=tool_bin/'arm-none-eabi-nm.exe';readelf=tool_bin/'arm-none-eabi-readelf.exe'
        symbols=subprocess.run([str(nm),'--defined-only',str(elf)],capture_output=True,text=True,check=True).stdout
        comment=subprocess.run([str(readelf),'-p','.comment',str(elf)],capture_output=True,text=True,check=True).stdout
        (output/(role+'_symbols.txt')).write_text(symbols,encoding='utf-8')
        (output/(role+'_compiler_comment.txt')).write_text(comment,encoding='utf-8')
        libs=inspect_map(mapfile)
        for library in libs:
            if Path(library['path']).name in ('libgcc.a','libc.a','libm.a','libg.a'):continue
            library['selected_source_notices']={}
            for member in library['selected_members']:
                name=member[:-4] if member.endswith('.obj') else member[:-2] if member.endswith('.o') else member
                library['selected_source_notices'][member]=list(source_index.get(name,{}).values())
        reports[role]=dict(elf=str(elf),elf_sha256=sha(elf),map=str(mapfile),map_sha256=sha(mapfile),libraries=libs,
            selected_archive_members=sum(x['selected_count'] for x in libs),md5_symbols=[s for s in symbols.splitlines() if re.search(r'\b\w*[Mm][Dd]5\w*$',s)],
            fatfs_symbols=[s for s in symbols.splitlines() if re.search(r'\bf_(open|read|close|mount)$',s)],
            distinction='LOAD is linker input; selected archive members are extracted, not proof every section survives --gc-sections; final nm records retained symbols')
    info=dict(passed=True,build_id=data['build_id'],sampling_hz=data['sampling_hz'],tools=tools,reports=reports,
        final_redistribution_cleared=False,pending=['Vendor toolchain source/patch correspondence for selected Newlib/GCC archive members','Applicable AMD EULA/IP redistribution terms for actual bitstream','Generated BSP configuration template provenance'],
        scope='actual app and FSBL binaries, maps and archive hashes; not bundled compiler, not legal clearance')
    (output/'summary.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k not in ('reports','tools')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--manifest',required=True);p.add_argument('--tool-bin',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.root,a.manifest,a.tool_bin,a.output)
