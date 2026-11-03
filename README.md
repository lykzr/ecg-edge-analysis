# ECG Edge：Zynq 心电边缘分析工程

**当前CNN/INT8演示接手入口：[优化版三核匹配镜像、Vivado实现设计和源码重建](board/cnn_fast_20261103/README.md)。** 克隆后可校验原字节BIT/ELF，直接临时JTAG运行；硬件源码及重建脚本随仓库提供。旧三核目录和 `releases/latest` 保留，不能混用。队友写设计报告见[比赛报告素材与实测数据](report/competition_brief.md)。

队友接手先看[Git接手与外部资料获取](docs/download_guide.md)，再看[剩余任务及最高优先级](report/handoff.md)。固定模型、参考结果及重建代码随Git；工具与数据按教程另取，不依赖原作者tmp。

面向正点原子领航者 V2（Zynq-7020）的心电边缘分析原型。当前交付以500Hz接收数字样本，在 ARM 端检测 QRS 波群中的 R 峰、计算相邻心拍间隔 RR 与心率，并在本机网页显示、保存波形和事件。正常结束后可以直接开启下一轮会话。

```text
ADS1292R → STM32 → JDY18 → 配套USB接收器 → 电脑解析与电压换算
                                               ↓ USB_UART
                              Zynq ARM：高通、QRS、RR、切拍和特征
                                               ↕ AXI
                                  PL：FP32 CNN / INT8 CNN / HGB
                                               ↓ ARM 汇总、UART
                                     电脑网页：显示、保存
```

也可回放标准CSV或厂商CSV；采集与板卡使用两个独立串口，网页不调用厂商EXE。未知类别 ? 不代表正常心拍。当前三核组合在同一PL镜像保留H27 FP32 CNN、W8A8 CNN和HGB Q40分类树，由网页选择并显示同板ARM/FPGA实测计时。ARM执行高通、检测与形态/历史特征，PL执行分类核心。CNN支持整段及边采边测，HGB保留整段；INT8模式另提供同拍四项计时。完整长时/无线验收与最终模型质量验收仍未完成。

| 目录 | 内容 |
| --- | --- |
| src/ | 板端C、硬件描述、电脑客户端和第三方源码 |
| build/、board/ | 网页构建、软硬件重建、下载及打包入口 |
| sim/、data/、model/ | 必要回归、参考实现、冻结参数与精选结果 |
| vivado/ | 可打开的文本工程及板级设计 |
| releases/latest/ | 匹配的当前JTAG/QSPI镜像与完整性清单 |
| docs/、report/ | 教程、协议、许可和实际实现报告 |
| skill/ | 产物校验、轨迹比对与下载诊断的可复用流程 |

## 板卡下载与烧录

当前 CNN 演示使用上方优化版三核入口。以下命令专用于旧 `releases/latest/` 的匹配运行时，不会启用新 CNN 三核。先运行 `python -B sim/check_system_release.py` 校验旧发布文件；下列 `<Vitis>` 和 `<唯一JTAG序列号>` 替换为本机工具路径与实际下载器序列号。

**JTAG临时运行（掉电失效）：** 断电并拔除所有可能供电的USB，将启动拨码设为JTAG（1=ON、2=ON，按实物编号复核），连接JTAG下载器并重新上电，执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -Xsdb '<Vitis>/bin/xsdb.bat' -CableSerial '<唯一JTAG序列号>'
```

**QSPI固化（掉电后保留）：** 同样先以JTAG模式上电，先核对文件，再执行带 `-Program` 的命令写入并校验Flash；该命令会覆盖QSPI偏移0的镜像区域。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/qspi/program_qspi.ps1 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/qspi/program_qspi.ps1 -Program -Xsdb '<Vitis>/bin/xsdb.bat' -ProgramFlash '<Vitis>/bin/program_flash.bat' -CableSerial '<唯一JTAG序列号>'
```

烧录成功后断电、拔除全部供电及USB，将拨码改为QSPI（1=ON、2=OFF），再上电。连接USB_UART，在网页完成一轮500Hz回放，确认收到 `DONE` 且上传、确认、回显点数一致。已有本版QSPI镜像时可直接按QSPI模式启动。

接线、下载器选择和排错详见完整教程：[JTAG临时运行](docs/download_guide.md#jtag临时运行)、[QSPI掉电启动](docs/download_guide.md#qspi掉电启动)。

## 网页启动

从项目根执行；既有验证环境为 Windows、Python 3.14、Node 24，硬件重建使用 Vivado/Vitis 2026.1。已有环境不必重复安装。

```powershell
python -m venv tmp/web_env
& ./tmp/web_env/Scripts/python.exe -m pip install -r src/web/requirements-lock.txt
./build/build_web.ps1
& ./tmp/web_env/Scripts/python.exe -B src/web/run.py
```

打开启动终端显示的本机地址，注册本地账号，进入“检测与加速”。启动、接线、回放、重建和故障处理统一见[使用教程](docs/download_guide.md)；报文及量纲见[接口协议](docs/protocols.md)；设计、证据及缺项见[当前实现与缺项](report/report.md)。自有许可见 [LICENSE](LICENSE)，第三方及网页来源的分发边界见 [third_party.md](third_party.md) 与[许可说明](docs/licenses.md)。

本工程直接通过 Git 仓库交付，不生成提交副本或压缩包。tmp/、本地资料、开发记录及历史发布由Git忽略；源码、依赖锁文件、当前发布、许可及必要证据保留。最后一版CNN候选的匹配镜像、离线校验和重建入口见[独立交接目录](board/cnn_demo_20261103/README.md)；该目录与正式latest分开。

提交前运行 python -B sim/check_repository.py、python -B sim/check_checkout.py 和 python -B sim/check_system_release.py，分别核对Git跟踪边界与文档链接、源码结构和发布身份，不替代构建或实板验收。提交及推送由负责人单独执行。
