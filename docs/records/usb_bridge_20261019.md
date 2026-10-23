# 电脑送样与USB_UART双向中转记录

## 目标与路线

2026-10-19，用户确认电脑↔Zynq使用板载USB_UART，并授权先修订计划/协议，再实现电脑输入与双向中转、完成可离线验证部分。

固定路线：ADS1292R→STM32→蓝牙→电脑→USB_UART→Zynq，Zynq经同一USB_UART返回运算结果。电脑保留原码并显示/中转，不把PC运算替代既有ARM/FPGA对比目标。厂商10/34字节差异只属于STM32采集输出段，不属于芯片SPI或Zynq结果协议。

**流式程序与本次接收候选均未上板验证。smoke既有板上通过证据保持独立，不能据本轮软件检查勾选B11。**

## 资料与环境

沿用本机Python 3.14.7、GCC及Vitis 2026.1，无新增依赖。此前已读ADS包的DOCX/核心源码、A盘V3.9底板图第6页及Vitis指南第201/205页，确认CH340C/P5双向通路和UART0/MIO14接收、MIO15发送；实物版本/跳帽/持续负载仍待验。没有在原资料目录构建、修改或分发原件。

PS复用已构建的独立500Hz XSA/bit/ps7_init，未更改PS7/DDR/MIO/时钟/XDC或RTL。既有360Hz共享工程、smoke、releases/latest、训练基线和模型输入协议保留。源ADC配置/蓝牙型号/透传方式、通道/标定与源丢样仍未确认。

## 修改和取舍

先更新report/project_plan.md、capture.md、system.md及docs/uart_protocol.md、ads1292.md，清除默认路线待选/电脑送样待确认等过期表述。保留360Hz旧smoke、500Hz新候选和144Hz模型输入各自语义，不全库替换360。

新增[ECG-IN-1](../bridge_protocol.md)：I初始化、D最多32点、F结束，输入和A确认带独立CRC32；PC一包在途，不自动重传。分包、重复、乱序、错误CRC或新会话中途进入均可导致非幂等AXI重复写，因此本版选择停止留证、重新配置PL后再开始，未擅自添加运行时RESET/SET_RATE。Zynq结果保持ECG-UART-1，A确认不混进旧K/E解析，结果行仍无CRC，不声称整条链路已受CRC保护。

新增src/ps/ecg_bridge/{main.c,bridge.c,bridge.h,README.md}：实际接收/校验后按序写PL、唯一FIFO消费者、回传实际提交值/事件、独立有界发送队列。数据来自电脑，不再自行造样；源时轴按序号和500Hz解释，不按蓝牙到包时间计RR。批末暂留1ms观察FIFO，它是候选策略，不是已测硬件时序保证。初始化只核对可观察残留；硬件无可读样本计数，不能据此证明内部状态全新，新会话仍须复位并重配PL。

新增电脑中转CLI与模块：ecg_bridge.py/core、ecg_capture.py、ecg_input_protocol.py、ecg_duplex.py。原WindowsSerial及Tk界面不改；派生适配增加部分写，独立管理采集连接和USB_UART双向连接。厂商入口显式选择版本、帧起点、通道、算术位移/饱和；保留二进制和两个24位码，再生成拟送int16。来源/500Hz须显式声明，不能由文件名或收到速度推定；无源序号时丢样保持未知。

记录分开保存capture.bin/adc.csv、normalized.csv、upload.log、usb_rx.log、controls.log及results/下既有结果记录；同一次运行的数据合计默认64MiB，超过立即失败，不静默删点、补零或覆盖历史。成功需确认、回传逐值/序号、完整END统计和关闭均通过。上传日志只反映驱动成功报告写入的字节，不证明物理发送。

复用board/build_ecg_stream.py的构建流程，默认仍为ecg_stream；增加独立board/build_ecg_bridge.py选择接收组件，不覆盖已有工作区/镜像。维护目录README、文档导航、测试说明和交接清单。现有GUI可回放results/raw.log，双连接实时GUI控件未实现；不把CLI结果说成GUI或实串口验收。

## 实际验证

命令与完整日志见[tmp验证目录](../../tmp/usb_bridge_validation_20261019/)和[测试摘要](../../tmp/usb_bridge_validation_20261019/tests.json)。本机用已有qrs_benchmark_env解释器执行，以下通用命令从项目根运行：

```powershell
python -B -m unittest discover -s sim -p test_usb_bridge.py -v
python -B -m unittest discover -s sim -p test_ps_stream.py -v
python -B -m unittest discover -s sim -p test_ads1292.py -v
python -B -m unittest discover -s sim -p test_pc_monitor.py -v
python -B -m unittest discover -s sim -p test_pc_serial.py -k NativeTests -v
```

共61项通过，无跳过：新中转18项、合成流9项、ADS解码14项、PC核心14项、原只收Windows适配6项。最后对中转CLI的摘要/限额参数维护后，18项重新运行并通过；其余源码未改，不重复扩展全库训练测试。没有运行Tk隐藏窗口测试或人工视觉检查。

- 编译实际PS bridge.c为共享库，由ctypes注入分块/限速假串口和原检测器500Hz整数参考AXI。不是另一份PS协议实现，也不是实际RTL/PS外设执行。
- 5003点脉冲完整双向传输，上传/实际AXI提交/回传逐值相同；10个事件位置70+500*i，首RR0、其余500，后续心率60。保持源丢样未知，未混用采集编号与ADC计数。
- 独立执行中转CLI：DOCX版本厂商原文1004点，显式限制送1003点，原二进制逐字节保留，1003点回传完整，额外观察点保留原码；A控制行未进入results/raw.log。
- 模拟500Hz采集，每8ms集中交付4点；中转等待确认期间继续读取采集端，5003个满宽正负边界值完整送达，缓存有界。这是受控分包/字节时序模型，不是蓝牙或USB实际吞吐测量。
- 错CRC/错误方向、参数不符、残留PL、序号缺口/重复、新会话、越界样本、残行/长行、错误总量、错误确认、队列满、零写入、UART停滞、时钟回退、CSV错误采样率和记录限额均有失败检查。无自动补点/重复送PL。
- 现有PC无界面回放本轮1003点/2事件结果，raw.log、samples.csv、events.csv、status.csv、sessions.jsonl五文件逐字节一致，见[回放核对](../../tmp/usb_bridge_validation_20261019/replay.json)。不是GUI视觉验收。

## 失败与纠正

首轮测试适配器误调用Detector.step，实际接口为tick；ctypes默认忽略回调异常，造成事件缺失并输出大量异常。修正接口，并增加回调异常立即失败的独立检查，防止假外设错误被误计为通过。该错误在测试适配器，不作为板端故障或算法准确率结论。

检查时发现时钟回退可能被后续无符号超时计算覆盖错误原因，修正为立即退出并保留CLOCK_REVERSED。第一轮ELF因此成为历史候选，保留在tmp/ecg_bridge/vitis_workspace；最终源码另在新工作区构建，旧ELF不冒充最终版本。

## 最终构建与交付边界

最终工作区：tmp/ecg_bridge_final/vitis_workspace，组件ecg_platform/ecg_bridge，运行配置ecg_bridge_app_hw_1。Vitis编译链接成功；[构建日志](../../tmp/usb_bridge_final_vitis_20261019.log)、[来源/产物清单](../../tmp/ecg_bridge_final/vitis_workspace/build_manifest.json)。最终ELF为ecg_bridge/build/ecg_bridge.elf，294076字节，SHA256：

```text
049fceb91c6d29a02747e68bc163668c03ac4947d9184e76e4cd6c53cbc124b5
```

本机该工作区是本轮最终候选，默认tmp/ecg_bridge的首次构建只作历史；跨电脑按[使用说明](../bridge.md)在新目录重建。没有修改latest、打包BOOT.BIN、连接板卡、烧录或提交推送。

仍待验证：实际蓝牙和固件版本/起始帧边界、真实500Hz/通道/标定、USB全双工负载和驱动/拔插、真实PL事件/时轴/尾部行为、完整GUI接入、滤波/切拍/CNN/INT8/FPGA分类及ARM对照。模型训练未恢复。计划仅勾选B08/B09/B10离线子项，不勾选整体或B11上板项。改前备份tmp/backup/usb_bridge_20261019_01；保护哈希与最终检查见[verification.json](../../tmp/usb_bridge_validation_20261019/verification.json)。

## 2026-10-19补记：统一中转文件命名

按用户要求将相同功能的文件集中到同一命名前缀，算法、线上报文和板端源码不变。上文旧命令和源码名称记录的是当时操作；以下为当前入口映射，旧派生目录和构建清单不改写：

| 原位置 | 当前位置 |
| --- | --- |
| src/pc/ecg_input_protocol.py | src/pc/ecg_bridge_protocol.py |
| src/pc/ecg_capture.py | src/pc/ecg_bridge_capture.py |
| src/pc/ecg_duplex.py | src/pc/ecg_bridge_serial.py |
| docs/pc_bridge.md | docs/bridge.md |
| docs/usb_input.md | docs/bridge_protocol.md |
| sim/test_usb_bridge.py | sim/test_ecg_bridge.py |
| sim/bridge_host.c | sim/ecg_bridge_host.c |

同步导入、测试编译引用、交接清单、目录说明和计划链接；历史记录仅修复说明文档超链接并追加本更名记录。备份原字节及映射见tmp/backup/bridge_names_20261019_01/manifest.json。当前测试命令为`python -B -m unittest discover -s sim -p test_ecg_bridge.py -v`，18项通过；命令行帮助和checkout检查通过（155文件、60份Python语法、29项模型基线）。测试原始输出tmp/bridge_names_test_20261019.log，最终范围和链接检查tmp/bridge_names_verification_20261019.json。

核对根README、资料索引、latest、板端C源码和现有ELF共24项哈希不变，未因此重建ELF或改既有发布。测试仍为受控串口/AXI软件闭环，流式及双向中转程序仍未上板。未操作Git、模型训练、板卡或Flash。
