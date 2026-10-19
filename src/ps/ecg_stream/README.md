# PS数字合成流

独立于ecg_smoke的裸机候选应用。main.c适配领航者V2现有UART0/AXI外设与PS全局计时器；stream.c/stream.h实现定时调度、合成输入、FIFO消费和有界协议发送。默认使用独立500Hz/120ms/200ms硬件，初始化核对PL只读参数；不匹配即拒绝送样，不能当作ADC驱动、数字滤波或CNN推理。

先由build/stream_500.tcl在新的tmp/ecg_stream_500生成匹配硬件，再由[构建脚本](../../../board/build_ecg_stream.py)在新的tmp工作区生成stream_build.h和ELF，不修改源码目录或smoke。操作、参数、报文与限制见[PS流式应用说明](../../../docs/ps_stream.md)，协议见[UART定义](../../../docs/uart_protocol.md)。主机假外设验证入口为sim/test_ps_stream.py；主机通过不能代替BSP构建、真实节拍或板上验收。
