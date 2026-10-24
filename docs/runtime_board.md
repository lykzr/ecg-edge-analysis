# 冻结QRS与切拍的ARM运行

当前正常500Hz下载入口为[release/download.cmd](../releases/latest/runtime500/download.cmd)，支持标准CSV和经客户端去直流/标称归一化的厂商ADC输入。按[下载教程](download_guide.md#当前项目直接下载新版)使用，无需依赖历史tmp。下文360Hz是独立冻结回归，不作为厂商入口。

## 分工和适用输入

电脑负责接收/保存、明确的输入换算、USB_UART上传、显示和保存返回结果；ARM运行冻结360Hz QRS、切拍、窗口/RR预处理及分类接口管理。未来FPGA负责最终合格INT8模型核心，当前没有最终模型或该核心。不能把本候选称完整系统已交付。

本候选仅接360Hz、4096单位/mV的int16标准样本，适用于已知公开数据回放。真实ADS1292R源为500Hz；其原码、真实标定和新QRS500Hz衔接没有获验收。不得把500Hz按360Hz直接发，不把CH2右移8当已标定单位。厂商34字节→电脑采集、ECG-IN-1→ARM、ECG-UART-1→电脑仍为三段协议。

## 构建和匹配组合

已有Vitis2026.1下从项目根运行；ECG_RUNTIME_WORKSPACE可指定新的项目tmp英文路径，已存在则拒绝覆盖。

```powershell
& '<Vitis>/bin/vitis.bat' -s board/build_runtime.py
```

脚本核对latest/smoke匹配bit/XSA/ps7_init，创建独立平台/应用ecg_runtime，显式libm、O2、关闭浮点融合及128KiB应用栈。build_manifest.json记录所有源和匹配产物SHA，不需要复制整个历史工作区。算法使用固定缓存，不依赖模板默认8KiB堆；不改PS7/DDR/MIO。

## GUI运行和显示

1. 电源、JTAG、USB_UART连接按下载教程。Vitis Set Workspace选择本次新工作区，Component选ecg_runtime，配置名ecg_runtime_app_hw_1。
2. 本次生成配置已核对系统复位、重新配置PL、ps7_init及核0对应ELF；每次错误后重新Run建立新会话。自动化只通过Tcl临时JTAG验证，GUI Run本身仍需人工操作核对。
3. 启动现有客户端`python -B src/pc/ecg_monitor.py`，打开“送样 / 双向中转…”，识别当前Zynq USB实例及COM。不要同时用其他终端占用串口。
4. 点击新入口“360Hz标准CSV → Zynq…”。此入口使用独立后台RuntimeWorker和runtime360合同；厂商CSV/蓝牙入口现在使用新500Hz应用；不能选360Hz应用混用。
5. 规范CSV首行为index,sample,fs,scale；index从0连续、sample为int16，逐行fs=360、scale=4096。可从已有公开数据导出：

```powershell
python -B data/export_runtime_samples.py --raw <已获取MIT数据目录> --record 100 --seconds 30 --output tmp/public100_new.csv
```

启动H表明初始化完成，电脑才发I，避免在算法初始化时撑满64字节UART接收FIFO。真实会话的H仍使用电脑的session；boot H只作为就绪控制旁证保存，不当作真实采样会话。完整结束须核对上传/确认/回传相同、END/DONE、事件/窗口及无错误。未知模型输出?，不当正常N。

## 自动实板验证

先核唯一板卡/JTAG、实际USB实例及匹配清单，硬件服务需本机3121就绪；用户授权后才执行。命令参数不复制本机COM号：

```powershell
python -B board/verify_runtime.py --manifest <新工作区/build_manifest.json> --xsdb <Vitis/bin/xsdb.bat> --cable <序列号> --port <COM> --device-id '<USB实例>' --raw <MIT数据目录> --record 100 --seconds 30 --output tmp/runtime_board_new
```

该验证以现有软件参考生成事件和128点窗口，实际USB_UART发送到ARM后逐项对照。须显式构建ECG_RUNTIME_TRACE=1（完整入口-Trace 1）才能输出用于核对float32的窗口调试L分块；正常运行默认关闭窗口跟踪以避免高负载积压。整体耗时不当作纯计算延迟。只通过原H/W/E/T/L及ECG-IN-1，不自创分类回填。验收从传入清单提取匹配硬件，不再固定引用旧发布路径。

错误验收另用board/verify_runtime_faults.py相同身份/镜像参数，分别新JTAG验证坏CRC、半帧、停流。输入错误后停机保存现场，不重传；重新Run后新session、清RR/模板/缓存，不跨断连续算。物理拔线/重插及真实无线丢包仍需实物验收。

## 离线复现

QRS环境运行test_ps_runtime.py（已有GCC编译实际C并对照窗口/事件）、test_runtime_link.py及test_runtime_worker.py；ECG_HOST_CC可给出已有GCC路径。完整42条事件移植对照由data/verify_ps_runtime.py提供，显式指定raw/golden/executable/output；golden可由冻结360Hz参考重新生成，不要求他人拿作者tmp。C主机入口sim/ecg_runtime_host.c读取int16小端。

正式C构建不需SciPy；resample360.h已保存系数。已有SciPy环境可用build/generate_runtime_coeffs.py --output <新文件>独立复核，不能覆盖旧文件。实际结果和失败见[实做记录](records/system_port_20261024.md)。人工视觉、真实采集、500Hz、最终模型/INT8/PL继续单独验收。

当前源码完整重建可使用board/rebuild_system.py；ECG_RUNTIME_HARDWARE仅显式指向带hardware_manifest.json的新tmp硬件目录，默认仍用已验smoke组合。新构建保留ecg_runtime.map链接图；新镜像未上板前不继承旧验收。

## 500Hz ARM应用

设置ECG_RUNTIME_RATE=500并选新工作区后构建ecg_runtime500，PC选择500Hz标准CSV入口；默认360Hz构建保留。源单位、身份、时轴和复现入口见[500Hz说明](rate500.md)。独立ELF不覆盖旧应用/发布；未核实唯一Zynq USB_UART身份时不打开未知端口或自动下载，离线通过不能继承旧360Hz实板成绩。


## 新500Hz数字验收与当前交付

当前本地JTAG入口为releases/latest/runtime500/run_runtime500.tcl，使用同目录匹配硬件与正常ELF。逐窗口调试仍需独立ECG_RUNTIME_TRACE=1镜像，不能把调试版替代正常持续流配置。

离线准备：`python -B board/verify_runtime500.py --prepare --raw <已下载MIT目录> --output tmp/fixture_new`，只使用已知100/105和合成信号。实板入口同脚本，参数为`--manifest <匹配500Hz构建清单> --fixtures <fixture目录> --case record100 --xsdb <XSDB路径> --cable <唯一序列号> --port <COM> --device-id <USB实例> --output tmp/board_new`；可用`--worker`走客户端后台。需要实际板卡和本会话授权，命令本身不是授权。错误脚本verify_runtime_faults.py用显式`--rate 500`，默认360保留。

当前新500Hz数字板测及限制造成的真实边界见[记录](records/runtime500_board_20261024.md)。自动后台不是人工界面验收，真实ECG设备与无线仍另验。

## 当前交接与掉电运行

当前500Hz应用已固化到本机板卡QSPI。已写同版镜像时直接QSPI上电，有限会话结束后PS复位；另一块板卡先核对匹配组合，按docs/download_guide.md的QSPI入口操作。JTAG仍是临时下载。完整未完成项统一见report/交接.md，验收见docs/records/qspi_20261025.md；不将数字CSV回放当真实无线、标定或CNN完成。路径均相对仓库根。
