"""核对双协议HGB构建后打包QSPI候选；默认不连接或写入板卡。"""
from pathlib import Path
import argparse,hashlib,json,shutil,struct,subprocess
ROOT=Path(__file__).resolve().parents[1]
def row(p):return dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def prepare(manifest,bootgen,output):
    manifest=Path(manifest).resolve();meta=json.loads(manifest.read_text())
    if meta.get('application')!='batch' or not meta.get('dual_protocol'):raise ValueError('须为保留既有QRS通信的双协议构建')
    for name,value in meta['files'].items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if row(p)!=value:raise ValueError('构建文件变化：'+name)
    for name,h in meta['sources'].items():
        p=(ROOT/name).resolve();p.relative_to(ROOT)
        if row(p)['sha256']!=h:raise ValueError('构建源码变化：'+name)
    output=Path(output).resolve();output.relative_to(ROOT/'tmp')
    if output.exists():raise FileExistsError(output)
    fsbl=[ROOT/n for n in meta['files'] if n.endswith('/fsbl.elf')]
    bit=[ROOT/n for n in meta['files'] if n.endswith('.bit')]
    assert len(fsbl)==len(bit)==1
    qspi=output/'qspi';qspi.mkdir(parents=True)
    components={}
    for role,p,name in [('fsbl',fsbl[0],'qspi/fsbl.elf'),('bit',bit[0],'hardware/ecg_system_candidate.bit'),('app',ROOT/meta['elf'],'prebuilt/ecg_hgb.elf')]:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        components[role]=dict(path=name,**row(target))
    (qspi/'boot.bif').write_text('the_ROM_image:\n{\n [bootloader] fsbl.elf\n ../hardware/ecg_system_candidate.bit\n ../prebuilt/ecg_hgb.elf\n}\n',encoding='ascii')
    for args,name in [(['-arch','zynq','-image','boot.bif','-o','BOOT.BIN'],'bootgen.log'),(['-arch','zynq','-read','BOOT.BIN'],'boot_read.log')]:
        cmd=[str(Path(bootgen).resolve()),*args]
        invocation='& '+' '.join("'"+v.replace("'","''")+"'" for v in cmd)+'; exit $LASTEXITCODE'
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',invocation],cwd=qspi,capture_output=True,timeout=90)
        (qspi/name).write_bytes(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Bootgen失败，保留日志')
    blob=(qspi/'BOOT.BIN').read_bytes()
    if len(blob)>33554432 or struct.unpack_from('<II',blob,32)!=(0xaa995566,0x584c4e58):raise ValueError('QSPI镜像容量或启动头错误')
    for name in ('program_qspi.ps1','probe_qspi.tcl','reset_qspi.tcl'):shutil.copyfile(ROOT/'board/runtime_handoff'/name,qspi/name)
    identity=row(output/'prebuilt/ecg_hgb.elf')['sha256'][:16]
    receipt=dict(schema=1,build_id=identity,flash_type='qspi-x4-single',offset=0,capacity_bytes=33554432,
        components=components,model=meta['model'],source_manifest_sha256=row(manifest)['sha256'],
        files={p.relative_to(qspi).as_posix():row(p) for p in qspi.iterdir() if p.is_file()},
        programming_verified=False,cold_boot_verified=False,scope='packaging only; explicit -Program and current board authorization required')
    (qspi/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt));return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','bootgen','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();prepare(a.manifest,a.bootgen,a.output)
