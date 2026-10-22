"""从匹配的已验证输入生成系统交付候选；不发布、不连接板卡、不删除历史。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
VERSION='20261021-system-jtag-v1'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row(path):
    return dict(bytes=path.stat().st_size,sha256=digest(path))


def write_manifest(directory,version,**metadata):
    files={p.relative_to(directory).as_posix():row(p) for p in sorted(directory.rglob('*'))
           if p.is_file() and p!=directory/'manifest.json'}
    payload=dict(schema=1,version=version,**metadata,files=files)
    (directory/'manifest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload


def package(output,smoke,workspace,hardware):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp')
    if output.exists():raise FileExistsError('候选输出已存在，停止避免覆盖')
    smoke=Path(smoke).resolve();workspace=Path(workspace).resolve();hardware=Path(hardware).resolve()
    build=json.loads((workspace/'build_manifest.json').read_text(encoding='utf-8'))
    if build['component']!='ecg_bridge' or build['sample_rate_hz']!=500:
        raise ValueError('须提供已验证500Hz bridge构建清单')
    for name,key in [('ecg_system_candidate.xsa','xsa_sha256'),('ecg_system_candidate.bit','bit_sha256'),('ps7_init.tcl','psinit_sha256')]:
        if digest(hardware/name)!=build[key]:raise ValueError('匹配硬件不同: '+name)
    elf=workspace/'ecg_bridge/build/ecg_bridge.elf'
    if digest(elf)!=build['elf_sha256']:raise ValueError('ELF与构建清单不同')
    for name,expected in build['source_sha256'].items():
        if digest(ROOT/'src/ps/ecg_bridge'/name)!=expected or digest(workspace/'ecg_bridge'/name)!=expected:
            raise ValueError('正式/导入源码与构建清单不同: '+name)
    old_manifest=json.loads((smoke/'manifest.json').read_text(encoding='utf-8'))
    for name,entry in old_manifest['files'].items():
        if row(smoke/name)!=dict(bytes=entry['bytes'],sha256=entry['sha256']):raise ValueError('smoke交付不完整: '+name)
    output.mkdir(parents=True)
    shutil.copytree(smoke,output/'smoke')
    # 新交付说明可修复链接，历史latest会原字节归档；验收核心不改。
    p=output/'smoke/README.md';text=p.read_text(encoding='utf-8')
    text=text.replace('# 当前发布：ECG smoke / JTAG','# smoke独立回归组件 / JTAG')
    text=text.replace('../../docs/records/','../docs/records/')
    p.write_text(text,encoding='utf-8')
    # 只更新新副本中受修改的README与manifest摘要，不改历史源/验收哈希。
    old_manifest['files']['README.md'].update(row(p))
    (output/'smoke/manifest.json').write_text(json.dumps(old_manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    artifacts=json.loads((output/'smoke/artifacts.json').read_text(encoding='utf-8'))
    artifacts['publishedLocation']='releases/latest/smoke'
    for entry in artifacts['files']:
        if entry['path'] in ('README.md','manifest.json'):entry.update(row(output/'smoke'/entry['path']))
    (output/'smoke/artifacts.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sources={}
    def copy(source,target):
        source=Path(source);target=output/target
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        sources[target.relative_to(output).as_posix()]={**row(source),'source':source.relative_to(ROOT).as_posix()}
    for name in ('ecg_system_candidate.bit','ecg_system_candidate.xsa','ps7_init.tcl'):
        copy(hardware/name,'bridge/hardware/'+name)
    copy(elf,'bridge/prebuilt/ecg_bridge.elf')
    for name in ('run_bridge.tcl','run_bridge.ps1'):
        copy(ROOT/'board/bridge_handoff'/name,'bridge/board/'+name)
    for name in ('build_ecg_stream.py','build_ecg_bridge.py'):
        copy(ROOT/'board'/name,'board/'+name)
    copy(ROOT/'board/bridge_handoff/create_workspace.py','board/create_bridge_workspace.py')
    for folder in ('pc','ui'):
        for p in sorted((ROOT/'src'/folder).glob('*.py')):copy(p,'src/'+folder+'/'+p.name)
    copy(ROOT/'src/reference/ads1292.py','src/reference/ads1292.py')
    for name in build['source_sha256']:
        copy(ROOT/'src/ps/ecg_bridge'/name,'src/ps/ecg_bridge/'+name)
    copy(ROOT/'LICENSE','LICENSE')
    # 精选证据，不含用户CSV/模型/下载盘；离线检查可独立核对。
    evidence=['smoke_board_validation_20261017.md','bridge_board_20261020.md','system_rounds_20261020.md',
              'uart_bridge_paced_20261020_pass.log','uart_bridge_csv_20261020_pass.log','uart_bridge_synth_20261020_pass.log']
    for name in evidence:copy(ROOT/'docs/records'/name,'docs/records/'+name)
    for p in sorted((ROOT/'docs/records/smoke_board_20261017').iterdir()):
        if p.is_file():copy(p,'docs/records/smoke_board_20261017/'+p.name)
    for n in ('board_verification.json','tests.json'):
        copy(ROOT/'tmp/system_rounds_20261020'/n,'evidence/'+n)
    for case in ('paced_01','bad-crc_02','partial_03','idle_03','paced_03'):
        for n in ('summary.json','plan.json','usb_rx.log','upload.log'):
            copy(ROOT/'tmp/system_rounds_20261020'/case/n,'evidence/cases/'+case+'/'+n)
    (output/'bridge/README.md').write_text('''# USB_UART双向数字回放组件

仅使用本目录500Hz hardware与prebuilt/ecg_bridge.elf，不能混用smoke的360Hz硬件。板端接收ECG-IN-1、送原QRS检测器并返回ECG-UART-1；没有滤波、CNN或Flash功能。

从系统包根目录按[总入口](../README.md)运行。board/run_bridge.ps1先核验本组件文件，实际JTAG必须显式指定下载器序列号；每个新会话重新配置PL和系统。正常结束/错误后程序停止，不自动重连或重传。运行脚本仅完成路径/离线验证，未重新操作板卡；交付ELF/硬件本身的数字验收见[记录](../docs/records/system_rounds_20261020.md)。真实无线、人工GUI及心电检测效果未验收。
''',encoding='utf-8')
    write_manifest(output/'bridge','20261020-bridge-clock-jtag-v1',sample_rate_hz=500,
                   build_id=build['build_id'],elf_sha256=build['elf_sha256'],flash_programming='NOT_PERFORMED')
    (output/'third_party.md').write_text('''# 许可与交付边界

自有PC、PS、构建和运行脚本适用根LICENSE。Python/Tk、AMD工具/BSP/IP及生成的ELF、bit、XSA、ps7_init.tcl分别保留原有权利，不由MIT重新授权；使用者须有合法AMD工具及驱动。未包含安装器、厂商手册/上位机、原始人体CSV、模型数据或权重。smoke子组件的原许可说明继续适用；本包是本地团队交付，公开上传仍需逐项核查和另行授权。
''',encoding='utf-8')
    (output/'README.md').write_text('''# ECG系统数字验证交付 / JTAG

适用于正点原子领航者V2、Zynq-7020，工具Vivado/Vitis 2026.1；具体板卡修订由使用者核实。本包包含独立smoke回归、500Hz USB_UART双向中转和PC客户端。两套硬件成对存放，不能交叉使用。

| 目录 | 用途 |
| --- | --- |
| smoke/ | 360Hz合成自检、匹配硬件/ELF和原GUI工作区创建入口 |
| bridge/ | 500Hz电脑送样→原检测器→结果回传的匹配硬件/ELF |
| src/ui/、src/pc/ | PC窗口、采集/CSV及中转后台，无模型推理 |
| src/ps/、board/ | bridge源码、构建及接收方工作区入口 |
| docs/records/、evidence/ | 精选验收记录和核验摘要 |

## 使用客户端与中转

需Python3.10以上；GUI另需Tkinter，Windows串口用标准库，不安装本机专属环境。完整复制到可写英文路径后，在包根目录运行：

```powershell
python -B src/ui/main.py
```

主窗口可演示/回放/只收结果。“采集 / 厂商CSV…”只看来源；“送样 / 双向中转…”才连接Zynq。厂商CSV须为五列RawData，HeatData不是波形；实采为34字节格式，CH1呼吸、CH2心电。采集接收器与Zynq USB_UART是不同端口，按USB身份和实际来源选择，不照搬COM号。原码/送样int16/板端结果分开，未标定不显示mV；shift8不是已验证的最终算法幅值合同。记录默认在包内tmp/的新目录，不覆盖旧记录。

先核对供电、JTAG启动拨码和下载器序列号，启动本机hw_server；关闭占用Zynq串口的其他终端。替换实际AMD路径与下载器序列号：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File bridge/board/run_bridge.ps1 -VitisBin 'D:/AMDDesignTools/2026.1/Vitis/bin' -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File bridge/board/run_bridge.ps1 -VitisBin 'D:/AMDDesignTools/2026.1/Vitis/bin' -CableSerial '<实际序列号>'
```

看到ECG_BRIDGE_JTAG_STARTED后，在客户端中转窗口选择来源和实际Zynq口开始；一次会话结束或出错后重新执行JTAG入口，不只重启电脑计数。CheckOnly只校验文件；启动标记不代表功能验收。此操作复位系统、重新配置PL，JTAG掉电失效，不写Flash。板端运算结果不代表临床诊断。

## 用Vitis重建bridge工作区

使用AMD自带Vitis Python入口，在包根目录运行：

```powershell
& 'D:/AMDDesignTools/2026.1/Vitis/bin/vitis.bat' -s board/create_bridge_workspace.py
```

默认生成tmp/ecg_bridge/vitis_workspace，已有目录停止；可在-s后脚本参数加--workspace指定新的英文路径。Vitis欢迎页Set Workspace选此目录，FLOW Component选ecg_bridge，Run配置ecg_bridge_app_hw_1，启用Reset System、Program Device、PS初始化。当前包保留已验ELF，不声称每次重建出的新ELF自动继承上板通过；工作区生成后不要搬动。

## 独立smoke回归

进入smoke/后按[smoke说明](smoke/README.md)使用board/run_smoke.ps1或创建其独立Vitis工作区。成功要求完整串口最后PASS ECG_SMOKE failures=0且无FAIL。切回bridge时须重配其500Hz硬件。

## 验证范围与许可

数字回放、持续负载和故障拒绝依据[本轮记录](docs/records/system_rounds_20261020.md)，smoke依据[原证据](docs/records/smoke_board_validation_20261017.md)。真实无线、人工GUI、ADC节拍/幅值标定、心电准确率和CNN/INT8/PL分类未验收；新便携入口的离线检查不替代这些实测。无BOOT.BIN、FSBL或QSPI固化。文件与来源见manifest.json和artifacts.json，许可见[LICENSE](LICENSE)与[第三方边界](third_party.md)。本目录更新不等于Git提交或对外发布。
''',encoding='utf-8')
    artifacts=dict(version=VERSION,purpose='local system digital handoff, no public upload',
        smoke_core_unchanged=artifacts['validatedCoreFiles'],bridge_build=build,
        sources=sources,scope=dict(smoke='USER_REPORTED_PASS',bridge='FINITE_DIGITAL_BOARD_PASS',
          wireless=False,manual_gui=False,ecg_accuracy=False,cnn_int8_pl=False,flash=False))
    (output/'artifacts.json').write_text(json.dumps(artifacts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    write_manifest(output,VERSION,purpose='Navigator V2 digital system JTAG release',flash_programming='NOT_PERFORMED')
    return dict(version=VERSION,output=str(output),files=sum(p.is_file() for p in output.rglob('*')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--smoke',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--hardware',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(package(args.output,args.smoke,args.workspace,args.hardware),ensure_ascii=False))
