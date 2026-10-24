"""明确选择360/500Hz ARM应用，从正式源码重建软硬件，不操作板卡。"""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(out,vivado,vitis,hardware_from=None,rate=360,trace=0):
 if rate not in (360,500):raise ValueError('采样率只允许360或500')
 if trace not in (0,1):raise ValueError('窗口跟踪只允许0或1')
 out=Path(out).resolve();out.relative_to(ROOT/'tmp');out.mkdir(parents=True,exist_ok=False)
 protected={p.relative_to(ROOT).as_posix():sha(p) for folder in ['releases/latest','src/ps/ecg_runtime'] for p in (ROOT/folder).rglob('*') if p.is_file()}
 commands=[]
 def step(cmd,log,env=None):
  commands.append([x.as_posix() if isinstance(x,Path) else str(x) for x in cmd])
  with (out/log).open('wb') as stream:
   # 原生PowerShell按独立参数调用BAT，避免cmd的二次参数解析差异。
   script='& '+ ' '.join("'"+x.replace("'","''")+"'" for x in commands[-1])+'; exit $LASTEXITCODE'
   p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],cwd=out,stdout=stream,stderr=subprocess.STDOUT,env=env,timeout=3600,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
  if p.returncode:raise RuntimeError('阶段失败，见'+str(out/log))
 if hardware_from:
  hardware=Path(hardware_from).resolve();hardware.relative_to(ROOT/'tmp')
 else:
  step([Path(vivado)/'vivado.bat','-mode','batch','-log','vivado_tool.log','-journal','vivado_tool.jou','-source',ROOT/'build/rebuild_system.tcl','-tclargs',out/'hardware_build'],'vivado_stdout.log',dict(os.environ,TMP=out.as_posix(),TEMP=out.as_posix(),XILINX_LOCAL_USER_DATA="no"))
  hardware=out/'hardware_build/hardware'
 current=json.loads((hardware/'ecg_system.bd').read_text(encoding='utf-8'))['design']['components']
 saved=json.loads((ROOT/'vivado/ecg_edge/ecg_edge.srcs/sources_1/bd/ecg_system/ecg_system.bd').read_text(encoding='utf-8'))['design']['components']
 if current['processing_system7_0']['parameters'] != saved['processing_system7_0']['parameters']:raise ValueError('PS7参数与正式BD不一致，停止')
 if current['ecg_qrs_axi_0']['parameters'] != saved['ecg_qrs_axi_0']['parameters']:raise ValueError('ECG参数与正式BD不一致')
 files={p.relative_to(hardware.parent).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [hardware/n for n in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl')]}
 (hardware/'hardware_manifest.json').write_text(json.dumps(dict(files=files,scope='fresh360 hardware; no board acceptance'),indent=2),encoding='utf-8')
 env=dict(os.environ,ECG_RUNTIME_RATE=str(rate),ECG_RUNTIME_TRACE=str(trace),ECG_RUNTIME_WORKSPACE=str(out/'ws'),ECG_RUNTIME_HARDWARE=str(hardware))
 step([Path(vitis)/'vitis.bat','-s',ROOT/'board/build_runtime.py'],'vitis.log',env)
 manifest=json.loads((out/'ws/build_manifest.json').read_text())
 if manifest.get('sampling_hz')!=rate:raise ValueError('实际应用采样率与所选值不符')
 if manifest.get('window_trace')!=bool(trace):raise ValueError('实际窗口跟踪配置不符')
 changed=[n for n,h in protected.items() if sha(ROOT/n)!=h]
 if changed:raise ValueError('保护文件变更：'+str(changed))
 result=dict(passed=True,sampling_hz=rate,window_trace=bool(trace),commands=commands,hardware_files=files,elf=manifest['elf'],build_id=manifest['build_id'],ps_parameters_equal=True,ecg_parameters_equal=True,protected_files=len(protected),hardware_from=hardware.as_posix() if hardware_from else None,scope='fresh BD/synthesis/implementation/bit/XSA/ELF; no hardware execution or final CNN')
 (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--vivado-bin',required=True);p.add_argument('--vitis-bin',required=True);p.add_argument('--rate',type=int,choices=(360,500),default=360);p.add_argument('--trace',type=int,choices=(0,1),default=0);p.add_argument('--hardware-from',help='显式接续本轮已完成的新硬件目录，不冒称本次新建');a=p.parse_args();run(a.output,a.vivado_bin,a.vitis_bin,a.hardware_from,a.rate,a.trace)
