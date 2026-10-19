# USB_UART接收与结果返回

main.c适配现有领航者UART0、全局计时器和AXI接口；bridge.c/bridge.h实现ECG-IN-1有界接收、CRC32/序号检查、输入缓存、逐样本写PL、唯一FIFO消费及非阻塞结果发送。不会生成合成脉冲、配置ADS1292R、滤波或运行CNN。

仅匹配500Hz/120ms/200ms独立硬件；初始化核对配置并拒绝可观察的PL残留。硬件没有可读样本计数，检查不能证明所有内部状态全新；每个新会话仍须系统复位并重新配置PL，不能仅重置电脑计数。当前没有自动重传、运行时改率或跨会话复用能力。

构建入口为board/build_ecg_bridge.py，工作区默认tmp/ecg_bridge/vitis_workspace；读取匹配500Hz XSA/bit/ps7_init，不改合成ecg_stream或smoke。协议、电脑入口、命令和验收边界见[中转说明](../../../docs/bridge.md)与[输入协议](../../../docs/bridge_protocol.md)。

sim/test_ecg_bridge.py编译实际C核心，通过假串口和软件参考AXI进行离线闭环；通过不代表真实PS驱动/AXI/UART正确。RX硬件错误会在main.c以ecg_bridge_result=-7退出，不保证错误行可发送；其他错误同样须结合日志、缺失结尾和调试器状态判断。流式程序尚未上板验证，不作为当前release交付。
