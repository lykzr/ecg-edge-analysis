# PC离线监视器

ecg_uart.py负责有界行解析和字段校验；ecg_monitor_core.py负责会话/序号、演示源、记录及绘图数据；ecg_monitor.py提供Tkinter界面和无界面入口。全部使用Python标准库，不连接板卡或执行检测/分类模型。

在项目根运行`python -B src/pc/ecg_monitor.py`。依赖Python3.10以上及Tkinter，完整操作、命令行、输出和限制见[PC使用说明](../../docs/pc_monitor.md)，报文定义见[UART协议](../../docs/uart_protocol.md#13-pc软件v1实现约定)，针对性验证入口为`sim/test_pc_monitor.py`。
