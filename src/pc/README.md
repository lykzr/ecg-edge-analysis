# PC波形监视器

ecg_uart.py负责有界行解析和字段校验；ecg_monitor_core.py负责会话/序号、演示源、记录及绘图数据；ecg_serial.py提供Windows串口只收适配；ecg_monitor.py提供Tkinter界面和无界面入口。全部使用Python标准库，不执行检测/分类模型。演示/回放可跨平台使用，串口当前仅支持Windows。

在项目根运行`python -B src/pc/ecg_monitor.py`。依赖Python3.10以上，图形界面另需Tkinter。串口填写实际COM端口，界面采用115200/8N1/无流控；关闭其他占用该端口的软件。完整操作、命令行、输出和限制见[PC使用说明](../../docs/pc_monitor.md)，报文定义见[UART协议](../../docs/uart_protocol.md#13-pc软件v1实现约定)，针对性验证入口为`sim/test_pc_monitor.py`及`sim/test_pc_serial.py`。

## 独立双向中转

同一功能的文件统一使用`ecg_bridge_`前缀，后缀表示职责：

| 文件 | 职责 |
| --- | --- |
| ecg_bridge.py | 命令行入口 |
| ecg_bridge_core.py | 中转流程、队列和确认 |
| ecg_bridge_protocol.py | 电脑送样协议ECG-IN-1 |
| ecg_bridge_capture.py | 厂商采集帧解码与输入转换 |
| ecg_bridge_serial.py | Windows串口双向收发 |

ecg_bridge.py为命令行入口，ecg_bridge_core.py管理有界源队列/一包在途/确认与结果分流，ecg_bridge_protocol.py只负责ECG-IN-1，ecg_bridge_serial.py在只收适配上增加部分写，ecg_bridge_capture.py解析显式版本厂商帧及参数化24→16位转换。原Tk界面不增加中转控件，仍可回放本次results/raw.log；真实双连接GUI联调另验。命令见[中转说明](../../docs/bridge.md)，结果协议与采集厂商协议不混用。
