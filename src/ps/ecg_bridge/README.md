# USB_UART接收与结果返回

main.c适配现有领航者UART0、全局计时器和AXI接口；bridge.c/bridge.h实现ECG-IN-1有界接收、CRC32/序号检查、输入缓存、逐样本写PL、唯一FIFO消费及非阻塞结果发送。不会生成合成脉冲、配置ADS1292R、滤波或运行CNN。

bridge_time.h按已求值的频率将tick转微秒；不要把BSP无括号的COUNTS_PER_SECOND宏直接放在除法/取余表达式中。main.c先获取完整timer_frequency，避免宏展开改变优先级；构建脚本同时导入并校验该头文件。

仅匹配500Hz/120ms/200ms独立硬件；初始化核对配置并拒绝可观察的PL残留。硬件没有可读样本计数，检查不能证明所有内部状态全新；每个新会话仍须系统复位并重新配置PL，不能仅重置电脑计数。当前没有自动重传、运行时改率或跨会话复用能力。

构建入口为board/build_ecg_bridge.py，工作区默认tmp/ecg_bridge/vitis_workspace；读取匹配500Hz XSA/bit/ps7_init，不改合成ecg_stream或smoke。协议、电脑入口、命令和验收边界见[中转说明](../../../docs/bridge.md)与[输入协议](../../../docs/bridge_protocol.md)。

sim/test_ecg_bridge.py编译实际C核心和计时换算，通过假串口和软件参考AXI进行离线闭环；通过不代表真实PS驱动/AXI/UART正确。RX硬件错误会在main.c以ecg_bridge_result=-7退出，不保证错误行可发送；其他错误同样须结合日志、缺失结尾和调试器状态判断。有限数字回放上板证据见[验收记录](../../../docs/records/bridge_board_20261020.md)，当前作为系统release的bridge独立组件交付，smoke回归另留，也不代替真实无线、人工显示或算法准确性验收。
