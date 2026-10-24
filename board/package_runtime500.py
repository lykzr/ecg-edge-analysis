"""从已验500Hz组合生成精简JTAG候选；归档与替换由显式发布步骤完成。"""
import argparse,json,hashlib,shutil
from pathlib import Path
from runtime_artifacts import resolve_runtime_artifacts
ROOT=Path(__file__).resolve().parents[1]
VERSION='20261025-runtime500-jtag-v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def row(p):return dict(bytes=p.stat().st_size,sha256=sha(p))
def manifest(folder,**metadata):
 data=dict(schema=1,version=VERSION,**metadata,files={p.relative_to(folder).as_posix():row(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='manifest.json'})
 # 包含子清单，只有当前目录自身manifest不纳入自身哈希。
 data['files']={p.relative_to(folder).as_posix():row(p) for p in sorted(folder.rglob('*')) if p.is_file() and p!=folder/'manifest.json'}
 (folder/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return data

def package(build_manifest,receipt,output):
 build,paths=resolve_runtime_artifacts(build_manifest,expected_rate=500)
 if build['window_trace']:raise ValueError('正常发布不可开启完整窗口跟踪')
 receipt=Path(receipt).resolve();receipt.relative_to(ROOT);evidence=json.loads(receipt.read_text())
 if evidence.get('kind')!='vendor500_digital_board' or not evidence.get('adc_source_supported'):raise ValueError('新版必须提供本版本ADC/CSV数字实板收据')
 if not evidence['passed'] or evidence['production_build_id']!=build['build_id']:raise ValueError('未取得本生产版本完整数字验收')
 if evidence['production_elf_sha256']!=sha(paths['elf']):raise ValueError('实板ELF与发布ELF不同')
 for name,h in evidence['evidence'].items():
  p=(ROOT/name).resolve();p.relative_to(ROOT)
  if sha(p)!=h:raise ValueError('验收证据变化：'+name)
 output=Path(output).resolve();output.relative_to(ROOT/'tmp')
 if output.exists():raise FileExistsError(output)
 old=ROOT/'releases/latest';previous=json.loads((old/'manifest.json').read_text())
 for name,r in previous['files'].items():
  if row(old/name)!=r:raise ValueError('旧发布校验失败：'+name)
 shutil.copytree(old,output,ignore=lambda directory,names: ['runtime500','qspi'] if Path(directory)==old else []);target=output/'runtime500';target.mkdir()
 for role,name in [('bit','ecg_system_candidate.bit'),('xsa','ecg_system_candidate.xsa'),('init','ps7_init.tcl')]:
  dst=target/'hardware'/name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(paths[role],dst)
 (target/'prebuilt').mkdir();shutil.copyfile(paths['elf'],target/'prebuilt/ecg_runtime500.elf')
 script=(ROOT/'board/classification_handoff/run.tcl').read_text(encoding='utf-8')
 script=script.replace('if {$argc!=4} {error "Usage: run.tcl cable bit init elf"}\nlassign $argv cable bit init elf',
   'if {$argc!=1} {error "Usage: run_runtime500.tcl cable"}\nset cable [lindex $argv 0]\nset base [file dirname [file normalize [info script]]]\nset bit [file join $base hardware ecg_system_candidate.bit]\nset init [file join $base hardware ps7_init.tcl]\nset elf [file join $base prebuilt ecg_runtime500.elf]')
 script=script.replace('ECG_CLASS_JTAG_STARTED','ECG_RUNTIME500_JTAG_STARTED')
 (target/'run_runtime500.tcl').write_text(script,encoding='utf-8')
 formal={n:h for n,h in build['sources'].items() if not n.startswith('tmp/')}
 for name in ('src/ps/ecg_runtime/runtime.c','build/generate_rate500_runtime.py','board/build_runtime.py'):
  formal[name]=sha(ROOT/name)
 for name in ('run_runtime500.ps1','download.cmd'):shutil.copyfile(ROOT/'board/runtime_handoff'/name,target/name)
 for folder in ('src/pc','src/ui'):
  for p in sorted((ROOT/folder).glob('*.py')):formal[p.relative_to(ROOT).as_posix()]=sha(p)
 sub=manifest(target,adc_source_supported=True,accepted_sources=['REPLAY','SYNTH','ADC'],sampling_hz=500,window_trace=False,build_id=build['build_id'],elf_sha256=sha(paths['elf']),board_execution='FINITE_DIGITAL_BOARD_PASS',flash_programming='NOT_PERFORMED',source_sha256=formal)
 artifacts=json.loads((old/'artifacts.json').read_text());artifacts['version']=VERSION
 for key in ('qspi_build','qspi_receipt'):artifacts.pop(key,None)
 artifacts['scope']['flash']=False
 artifacts['sources']={name:value for name,value in artifacts['sources'].items() if not name.startswith('qspi/')}
 artifacts['runtime500_build']=dict(build_id=build['build_id'],sampling_hz=500,window_trace=False,elf_sha256=sha(paths['elf']),bit_sha256=sha(paths['bit']),xsa_sha256=sha(paths['xsa']),source_sha256=formal)
 artifacts['runtime500_build']['adc_source_supported']=True
 artifacts['runtime500_receipt']=receipt.relative_to(ROOT).as_posix()
 artifacts['scope']['runtime500']='FINITE_DIGITAL_BOARD_PASS'
 for name in ('run_runtime500.ps1','download.cmd'):
  artifacts['sources']['runtime500/'+name]=dict(source='board/runtime_handoff/'+name,**row(target/name))
 artifacts['evidence'].update({receipt.relative_to(ROOT).as_posix():sha(receipt),**evidence['evidence']})
 (output/'artifacts.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (output/'README.md').write_text("""# ECG系统JTAG交付

runtime500为当前500Hz ARM QRS/切拍程序，支持标准CSV及客户端内部处理后的厂商CSV/蓝牙采集输入。厂商CH2去直流/标称单位换算在仓库客户端内部完成，不是PC端QRS或CNN推理。

| 目录 | 用途 | 输入 |
| --- | --- | --- |
| runtime500/ | 当前ARM检测/切拍与双向收发 | 500Hz、4096单位/mV、REPLAY/SYNTH/ADC；无最终模型时类别未知 |
| smoke/ | 独立基础回归自检 | 板端合成样本 |
| bridge/ | 旧PL检测器回归 | 旧500Hz、scale=-1，仅显式legacy500 |

各组件使用自己的hardware、prebuilt和启动脚本，不交叉替换。正常运行关闭完整窗口跟踪。

## 下载与运行

Windows双击runtime500/download.cmd，按提示填写已安装的Vitis/bin/xsdb.bat路径及已核实的唯一JTAG序列号；也可在PowerShell指定参数：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -Xsdb '<Vitis>/bin/xsdb.bat' -CableSerial '<JTAG序列号>'
```

仅验证本地文件、不操作板卡：给同一入口加-CheckOnly。入口核对包内所有字节/SHA256，随后Tcl再次核对唯一Zynq-7020、复位、配置匹配PL/PS并下载应用。不写Flash，掉电或会话结束后重新下载；不需要管理员权限。ExecutionPolicy参数只作用于这次进程，不修改系统策略。

从仓库运行python -B src/ui/main.py，主窗口串口保持未连接，在送样/双向中转子窗口选择板卡USB_UART。厂商CSV用五列RawData按钮；蓝牙选择另外一个采集USB接收器端口。CH2自动去直流并按2.42V/PGA6标称换算，无需手动右移；参考/增益未实测标定。标准CSV须index,sample,fs,scale、fs=500、scale=4096，不再二次换算。

## 重建、许可与范围

正式源码/依赖和重建入口在仓库，见[下载教程](../../docs/download_guide.md)、[厂商输入](../../docs/vendor_input.md)和[构建说明](../../docs/system_checks.md)。本目录可单独用于JTAG，但客户端、许可原文、完整证据应随仓库查阅；没有作者tmp也能运行包内下载入口。

本地数字验收与来源见artifacts.json。真实无线/实际ADC节拍与标定、物理拔插/长时运行、新厂商界面人工检查和最终CNN/INT8/FPGA推理仍单独验收。QRS105噪声风险保留，不把有限数字回放当独立准确率或整机通过。

自有内容与第三方范围分别见LICENSE和third_party.md，原声明在仓库docs/licenses/，当前应用/配套FSBL实际组成见data/results/runtime500_components_20261025.json（FSBL未随JTAG包分发）。最终供应商工具链补丁/IP分发边界仍待核；本地更新不代表远端发布，也没有Flash固化。
""",encoding='utf-8')
 manifest(output,purpose='matched JTAG artifacts; sources, licenses and evidence stay in repository',flash_programming='NOT_PERFORMED')
 print(output)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('manifest','receipt','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();package(a.manifest,a.receipt,a.output)
