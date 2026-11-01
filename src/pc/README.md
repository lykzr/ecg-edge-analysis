# PC通信与数据后台

本目录负责协议、串口、采集、中转、记录和无界面命令行；Tk窗口与绘图在[src/ui](../ui/README.md)。后台使用Python标准库，不执行检测/分类模型；演示/回放可跨平台，串口当前仅支持Windows。

默认图形入口为[网页客户端](../../docs/download_guide.md)，由独立网页环境运行 `src/web/run.py`。`python -B src/ui/main.py` 是[Tk备用入口](../../docs/download_guide.md)，基础后台依赖Python3.10以上，Tk界面另需Tkinter；旧 `src/pc/ecg_monitor.py` 无参数仍转交Tk，`--headless` 保留命令行行为。网页依赖单独见其教程，不由基础后台要求推断。报文定义见[UART协议](../../docs/protocols.md)。

| 文件 | 职责 |
| --- | --- |
| ecg_monitor.py | 无界面结果接收/回放CLI及旧GUI兼容入口 |
| ecg_monitor_core.py | 会话、序号、演示源、数据模型和基础记录 |
| ecg_uart.py | ECG-UART-1结果解析 |
| ecg_serial.py、ecg_bridge_serial.py | Windows单向/双向串口适配 |
| ecg_ports.py、ecg_paths.py | 端口身份、项目位置与独立记录目录 |

## 采集与厂商CSV

ecg_capture_core.py负责五列RawData校验、原码恢复、34字节起始候选及后台完整记录；窗口为ui/capture.py。ecg_ports.py只读枚举Windows端口和USB身份，不发送探测命令。使用说明见[采集操作](../../docs/download_guide.md)，针对性检查为sim/test_pc_capture.py。

采集视图不构造ECG-UART-1报文、不运行QRS/CNN、不向Zynq送样。CSV滤波列仅为厂商保存的历史结果，实时来源未提供滤波。完整原文、双通道与算法预览分别保存在tmp/pc_capture_logs/的新目录；默认右移8位仅作int16算法预览，无物理标定含义。需要送样时使用单独的“送样 / 双向中转…”视图，避免串口所有者冲突。

## 独立双向中转

同一功能的文件统一使用`ecg_bridge_`前缀，后缀表示职责：

| 文件 | 职责 |
| --- | --- |
| ecg_bridge.py | 命令行入口 |
| ecg_bridge_core.py | 中转流程、队列和确认 |
| ecg_bridge_protocol.py | 电脑送样协议ECG-IN-1 |
| ecg_bridge_capture.py | 厂商采集帧解码与输入转换 |
| ecg_bridge_serial.py | Windows串口双向收发 |
| ecg_bridge_worker.py | 中转后台、采集与板端连接所有权、停止收尾 |
| ecg_bridge_records.py | CLI和中转后台共用的记录与额度 |

ecg_bridge.py为CLI入口；ui/bridge.py调用ecg_bridge_worker.py，后台从ecg_bridge_records.py取记录类，不反向依赖CLI。BridgeClient与CaptureWorker负责数据流，ui/plot.py由两个窗口共用，不借用另一窗口对象。命令见[中转说明](../../docs/download_guide.md)，结果协议与采集厂商协议不混用。

电脑送样客户端只显式接受QRS-ORIG-60或独立候选QRS-AUTOPEAK-60身份，其余会话/来源/采样率/能力仍严格核对；未知身份拒绝。候选前两秒只预热，位置保留原样本序号；不能因没有早期事件补造心拍。格式仍是ECG-IN-1输入、ECG-UART-1结果，详见[当前实现与缺项](../../report/report.md)。已验发布内的旧客户端只支持原检测器，候选请用正式源码入口。

## 冻结360Hz板端回放

送样子窗口新增“360Hz标准CSV → Zynq…”；由ecg_runtime_worker后台驱动runtime360客户机，电脑只发送、显示、记录，不在此客户端执行QRS/CNN。CSV必须index,sample,fs,scale且360Hz/4096单位；厂商CSV/蓝牙默认走新500Hz去直流/标称归一化，旧legacy500仅显式回归，不能相互替代。启动、停止/错误保存、重新Run的新会话和示例数据导出见[板端教程](../../docs/download_guide.md)。

中转摘要的timing为PC往返耗时，包含写入/通信/板端/读取；不当作推理时间。RuntimeWorker的maximum可配置记录总限额（默认64MiB、最少1024字节），到限额失败留前缀和摘要。见[测量说明](../../docs/download_guide.md)。

中转摘要sample_age_s为PC最后一段合法回传W后的接收间隔，不是源采样时间或断连证明；供界面提示历史数值。

500Hz标准输入使用RuntimeWorker(sampling_hz=500)和BridgeClient(profile='runtime500')；RuntimeWorker标准CSV默认360Hz不变；BridgeWorker与CLI厂商默认runtime500，legacy500须显式选择。500Hz单位必须明确为4096单位/mV，不能直接拿右移厂商码替代，详见[500Hz说明](../../docs/download_guide.md)。

标准CSV后台收到DONE后仍检查同次接收的残缺尾行，有残行必须失败保存，不当作完整成功。队列/发送/记录均有上限，不保证任意慢接收或无限时长。负载验证入口见[系统检查](../../docs/download_guide.md)。

厂商接入的NominalConverter只用标准库实现固定去直流/标称转换，CaptureWorker(normalization="nominal500")保存前后mV和转换参数；standalone采集预览仍可保留legacy_shift。协议、启动和失败行为见[厂商接入](../../docs/download_guide.md)。

网页通过ecg_web_service.py适配同一套后台，不另造采集/QRS/分类流程。该适配器本身仍仅依赖标准库，FastAPI和前端依赖在src/web单独声明；使用见[网页教程](../../docs/download_guide.md)。

网页可在start时注入on_complete回调，采集线程关闭后向现有分析队列提交完整记录。回调状态与任务号随会话持久化；独立Tk/命令行未注入回调时行为保持。HGB在网页模型独立进程执行，不写回或替代板端分类，详见[模型接入](../../docs/model_integration.md)。
