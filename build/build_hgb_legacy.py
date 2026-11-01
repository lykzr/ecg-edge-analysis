"""为双入口固件独立编译现有500Hz流式核心；不改其源码或模型符号。"""
from pathlib import Path
import hashlib
import subprocess
import runpy
ROOT=Path(__file__).resolve().parents[1]

def build(output, compiler):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp')
    output.mkdir(parents=True,exist_ok=False)
    generated=output/'generated'
    runpy.run_path(str(ROOT/'build/generate_rate500_runtime.py'))['run'](generated)
    inputs=[ROOT/'src/ps/ecg_hgb/legacy.c',generated/'link500.c',generated/'runtime500_bridge.c',
            ROOT/'src/ps/ecg_rate500/rate500.c',ROOT/'src/ps/ecg_rate500/pipeline500.c',
            ROOT/'src/ps/ecg_classification/classification.c']
    includes=[ROOT/'src/ps/ecg_hgb',ROOT/'src/ps/ecg_runtime',ROOT/'src/ps/ecg_rate500',ROOT/'src/ps/ecg_classification']
    # 与已有500Hz固件相同浮点选项；不强制包含HGB冻结符号头。
    flags=['-O2','-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-ffp-contract=off','-fno-fast-math','-fstack-usage']
    objects=[];commands=[]
    for i,p in enumerate(inputs):
        obj=output/f'legacy{i}.o'
        cmd=[str(compiler),*flags,*[f'-I{p}' for p in includes],'-c',str(p),'-o',str(obj)]
        subprocess.run(cmd,check=True,capture_output=True);commands.append(cmd);objects.append(obj)
    archive=output/'libhgb_legacy.a'
    subprocess.run([str(Path(compiler).with_name('arm-none-eabi-ar.exe')),'rcs',str(archive),*[str(p) for p in objects]],check=True,capture_output=True)
    headers=[p for folder in includes for p in folder.glob('*.h') if p.name!='frozen.h']
    sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs+headers+[ROOT/'build/generate_rate500_runtime.py',Path(__file__).resolve()]}
    return archive,sources,commands
