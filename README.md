# ECG Edge：Zynq 心电边缘分析工程

面向正点原子领航者 V2（Zynq-7020）的心电边缘分析原型。当前交付以500Hz接收数字样本，在 ARM 端检测 QRS 波群中的 R 峰、计算相邻心拍间隔 RR 与心率，并在本机网页显示、保存波形和事件。正常结束后可以直接开启下一轮会话。

```text
ADS1292R → STM32 → JDY18 → 配套USB接收器 → 电脑换算与去直流
                                               ↓ USB_UART
                                     Zynq ARM：QRS、RR、切拍
                                               ↓
                                     电脑网页：显示、保存
```

也可回放标准CSV或厂商CSV；采集与板卡使用两个独立串口，网页不调用厂商EXE。当前没有最终分类模型，未知类别 ? 不代表正常心拍。轻量卷积神经网络 CNN、8位整数 INT8 量化、FPGA整网推理及 ARM/FPGA 性能比较仍未完成，现有独立算子和 PL 回归不能替代这些目标。

| 目录 | 内容 |
| --- | --- |
| src/ | 板端C、硬件描述、电脑客户端和第三方源码 |
| build/、board/ | 网页构建、软硬件重建、下载及打包入口 |
| sim/、data/、model/ | 必要回归、参考实现、冻结参数与精选结果 |
| vivado/ | 可打开的文本工程及板级设计 |
| releases/latest/ | 匹配的当前JTAG/QSPI镜像与完整性清单 |
| docs/、report/ | 教程、协议、许可和实际实现报告 |

从项目根执行；既有验证环境为 Windows、Python 3.14、Node 24，硬件重建使用 Vivado/Vitis 2026.1。已有环境不必重复安装。

```powershell
python -m venv tmp/web_env
& ./tmp/web_env/Scripts/python.exe -m pip install -r src/web/requirements-lock.txt
./build/build_web.ps1
& ./tmp/web_env/Scripts/python.exe -B src/web/run.py
```

打开启动终端显示的本机地址，注册本地账号，进入“实时与板卡”。启动、接线、回放、重建和故障处理统一见[使用教程](docs/download_guide.md)；报文及量纲见[接口协议](docs/protocols.md)；设计、证据及缺项见[实现报告](report/report.md)。自有许可见 [LICENSE](LICENSE)，第三方及网页来源的分发边界见 [third_party.md](third_party.md) 与[许可说明](docs/licenses.md)。

提交副本按明确清单生成，不复制本地归档、账号数据库、环境、原始数据或工具缓存：

```powershell
python -B board/package_submission.py --output tmp/submission_new
```

输出目录必须不存在，检查收据写在输出目录旁。保留的参考实现是构建/回归依赖，不表示已部署功能。该副本供本地审阅；网页来源未带根许可，对外再分发仍需权利确认。操作不提交或上传代码。
