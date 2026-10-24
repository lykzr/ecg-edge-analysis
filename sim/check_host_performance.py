"""测当前主机C回放CPU时间和逻辑等待，不声称ARM/FPGA性能。"""
import argparse,hashlib,json,os,platform,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(output):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
    if not cc:raise RuntimeError('需要已有GCC，不安装')
    sources=[ROOT/'sim/ecg_perf_host.c']+[ROOT/'src/ps/ecg_runtime'/n for n in ('runtime.c','pipeline.c')]+[ROOT/'src/ps/ecg_classification/classification.c']
    cmd=[cc,'-O2','-std=c11','-ffp-contract=off','-I'+str(ROOT/'src/ps/ecg_classification')]+list(map(str,sources))+['-lm','-o',str(output/'perf.exe')]
    p=subprocess.run(cmd,capture_output=True,env=dict(os.environ,TMP=str(output),TEMP=str(output)),timeout=90)
    (output/'compile.log').write_bytes(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('编译失败')
    runs=[]
    for _ in range(3):
        p=subprocess.run([str(output/'perf.exe')],capture_output=True,timeout=90)
        if p.returncode:raise RuntimeError(p.stderr)
        row=json.loads(p.stdout);assert row['samples']==36000 and row['events']>0
        assert row['qrs_cpu_s']>=0 and row['pipeline_including_qrs_cpu_s']>=0
        runs.append(row)
    info=dict(passed=True,environment=platform.platform(),compiler=subprocess.check_output([cc,'--version']).decode(errors='replace').splitlines()[0],runs=runs,
              source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              inference=None,pl=None,scope='host CPU only; separate overlapping passes; not ARM/FPGA or end-to-end wall latency')
    (output/'summary.json').write_text(json.dumps(info,indent=2),encoding='utf-8');print(json.dumps(info))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);run(p.parse_args().output)
