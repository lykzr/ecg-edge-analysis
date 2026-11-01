"""用已有Vitis ARM交叉编译器生成可导入裸机工程的静态库；不连接板卡。"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
from export_hgb import export, ROOT


def build(output, cc):
    output=Path(output).resolve();cc=Path(cc).resolve()
    output.mkdir(parents=True,exist_ok=False)
    if not cc.is_file():raise FileNotFoundError(cc)
    ar=cc.with_name(cc.name.replace('gcc','ar'));size=cc.with_name(cc.name.replace('gcc','size'));nm=cc.with_name(cc.name.replace('gcc','nm'))
    if not ar.is_file() or not size.is_file() or not nm.is_file():raise FileNotFoundError('需要同工具链的ar、size与nm')
    model=export(output/'parameters')
    core=ROOT/'src/ps/ecg_hgb';native=ROOT/'model/inference/native'
    sources=[core/n for n in ('features.c','tree.c','prepare.c')]+[output/'parameters/hgb_parameters.c']
    sources += [native/n for n in ('pipeline500.c','rate500.c','classification.c','runtime500_bridge.c')]
    flags=['-std=c11','-O2','-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard',
           '-ffp-contract=off','-fno-fast-math','-fstack-usage','-Wall','-Wextra','-Werror',
           '-I'+str(core),'-I'+str(native),'-include',str(core/'frozen.h')]
    commands=[];objects=[]
    env=dict(os.environ,TMP=str(output),TEMP=str(output),TMPDIR=str(output))
    def run(cmd):
        commands.append(cmd)
        p=subprocess.run(cmd,capture_output=True,timeout=120,env=env)
        with (output/'compile.log').open('ab') as f:f.write(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
        return p.stdout.decode(errors='replace')
    version=run([str(cc),'--version'])
    for i,p in enumerate(sources):
        obj=output/f'part{i}.o';objects.append(obj)
        cmd=[str(cc),*flags,'-c',str(p),'-o',str(obj)]
        if p.parent==native:cmd+=['-Wno-error=misleading-indentation']
        run(cmd)
        data=obj.read_bytes()
        assert data[:4]==b'\x7fELF' and data[4]==1 and int.from_bytes(data[18:20],'little')==40,'不是ELF32 ARM对象'
    library=output/'libecg_hgb.a'
    run([str(ar),'rcs',str(library),*[str(p) for p in objects]])
    sizes=run([str(size),'-B',*[str(p) for p in objects]])
    symbols=run([str(nm),'-g','--defined-only',str(library)])
    for line in symbols.splitlines():
        parts=line.split()
        if len(parts)==3:
            name=parts[-1]
            assert name.startswith(('hgb_','ecg_hgb_')),'泄漏未隔离内部符号：'+name
    stack={}
    for p in output.glob('*.su'):
        for line in p.read_text().splitlines():
            parts=line.split('\t')
            if len(parts)==3:stack[parts[0]]=dict(bytes=int(parts[1]),kind=parts[2])
    result=dict(passed=True,scope='Cortex-A9 hard-float static library; no linked board application, ARM execution or Flash',
                model=model,compiler_version=version,commands=commands,size_output=sizes,stack=stack,symbols_isolated=True,
                arm_executed=False,hardware_operated=False,fits=0,
                library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_relative_to(ROOT) and p.parent!=output/'parameters'})
    result['sources'][Path(__file__).resolve().relative_to(ROOT).as_posix()]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for p in (core/'hgb.h',core/'frozen.h',ROOT/'build/export_hgb.py'):
        result['sources'][p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    (output/'build.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--cc',required=True,type=Path)
    args=parser.parse_args()
    result=build(args.output,args.cc)
    print(json.dumps({k:result[k] for k in ('passed','scope','library_sha256','arm_executed','fits')},ensure_ascii=False))
