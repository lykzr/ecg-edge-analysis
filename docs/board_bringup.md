# 领航者 V2：当前工程上板状态与 JTAG 下载步骤

核查日期：2026-10-13。本文是操作说明，不是上板成功记录。实物核心板/底板版本、JTAG 下载器型号仍待确认。

## 当前工程下载后会是什么状态

当前只有 PS7/AXI 硬件框架和 QRS 候选检测 RTL，没有 ECG 的 PS 应用、采集接口、显示驱动或串口结果输出程序。输入来自 PS 对 `0x43C00000` 的寄存器写入；PL 不会自行从串口或电极取样。

| 已做的动作 | 可以说明什么 | 预期现象及限制 |
| --- | --- | --- |
| 仅上电，未下载本工程 | 板卡供电和原有启动环境的状态 | 可能启动出厂程序，不能算 ECG 工程运行 |
| 仅下载本工程的新 `.bit` | PL 配置是否成功 | 可检查工具的 DONE 状态；不会自动显示 ECG、心率或打印串口结果 |
| 再按同一 XSA 初始化 PS/DDR/时钟/复位 | 系统是否具备访问 PL 的条件 | PL 时钟来自 PS 的 FCLK0，单独配置 PL 不能保证 PS 已正确初始化 |
| 再运行一个 PS 应用 `.elf` | ARM 程序是否执行 | Hello World 可以检查串口；ECG 回放应用才能送样并读取事件 |
| 用 ECG 回放程序处理固定数据并比对 | 数据链路和所测样本的检测表现 | 需要记录输入数、事件、RR、丢弃数和参考比对，不能凭一次打印宣称算法准确 |

当前实际 BD 使用 FCLK0 100 MHz；复位经 `proc_sys_reset`；ECG 默认 360 Hz、16 位有符号样本、FIFO 深度 8。AXI 读写见 [register_map.md](register_map.md)。没有用于用户 LED 闪烁的顶层接口，配置完成指示灯不代表 QRS 算法通过。

本地找到的唯一 `.bit`：`vivado/ecg_edge/ecg_edge.runs/impl_1/ecg_system_wrapper.bit`，文件时间为 2026-10-06 16:41:40，早于 2026-10-13 的 RTL 和 BD 修改。**它不是当前领航者修复版输出，不用于本次流程。**本轮在 `vivado/` 和 `tmp/` 搜索没有发现 `.xsa` 或 `.elf`。

## 文件之间的关系

| 文件 | 用途 |
| --- | --- |
| `.bit` | 配置 PL 的硬件逻辑，JTAG 临时下载 |
| `.xsa` | 向 Vitis 描述处理器、外设、地址和初始化信息；可包含 bitstream，是平台开发输入，不是直接运行的应用 |
| `.elf` | ARM 应用程序，用 Vitis/JTAG 下载并运行 |
| `ps7_init.tcl` / FSBL | 初始化本工程对应的 PS、DDR 和时钟等；必须与 XSA 和实物配置匹配 |
| `BOOT.BIN` | 后续制作的自启动镜像，本项目通常包含 FSBL、bitstream、应用 ELF |

开发阶段建议先用 JTAG。它配置 PL 并把应用下载到易失存储器；不写 QSPI/SD 内容，断电后本次临时下载的状态丢失。切回原启动模式后，板卡可按原有镜像启动。自启动镜像在 JTAG 路径稳定后再制作。

## 第一步：核对实物和连接

以下是 A 盘主目录指南的接法，执行前应把具体版本和接口丝印与实物核对；不能凭“领航者 V2”推断所有版本相同。

1. 断电后调整拨码、跳帽和连接线。记录核心板、底板丝印版本及下载器型号。
2. 外置、Vivado 支持的 JTAG 下载器：USB 端接电脑，下载线接底板 14-Pin JTAG 调试口，按下载器与板卡标识核对方向/1 脚。底板 14 针口和核心板 6 针口连接同一 JTAG 网络；本流程使用底板口，不同时接两个下载器。
3. 单独一根 USB 数据线接底板 `USB_UART` 与电脑，用于查看串口输出。**CH340 串口 USB 不能代替 JTAG 下载器。**串口口、USB HOST/SLAVE 不要混淆。
4. 主目录手册中，串口跳帽 `P5` 应连接串口芯片 RX 到 `PS_TX`、TX 到 `PS_RX`。核对实际丝印与匹配版本图纸，不根据照片猜引脚位置。
5. 匹配主目录手册的 `BOOT_CFG`：编号 1=ON、2=ON 是 JTAG；1=ON、2=OFF 是 QSPI；两位 OFF 是 SD。按开关 ON 丝印判断，不仅凭“朝上/朝下”。设置后再上电。
6. 用板卡匹配的电源供电。电脑应能识别 JTAG 下载器和串口 COM 口；缺驱动时先核查设备与系统，不自动运行下载盘安装器。
7. 串口参数采用 Hello World 示例的 115200、8 数据位、无校验、1 停止位、无流控；COM 号以本机设备管理器为准，不套用教程 COM3。

## 第二步：生成当前配置的新硬件文件

这一步是正式开始构建时的操作，本文没有执行。

1. 确认实际板卡参数依据，再在独立构建目录中用 `scripts/build_navigator_ecg_system.tcl` 生成/核对 BD。当前目录已迁移到 `C:/Users/23006/Desktop/ecg_edge`；旧日志和 XPR 中有旧路径，先验证实际加载与可重建性。
2. 确认顶层为 `ecg_system_wrapper`，器件 `xc7z020clg400-2`，当前 BD/RTL 源文件正确。
3. 重新运行综合、实现并检查时序及 DRC，通过后生成新 bitstream。不要只因旧 `.runs` 中存在 `.bit` 就跳过重建。
4. Vivado 中 `File > Export > Export Hardware`，导出当前硬件 XSA，包含刚生成的 bitstream。中间文件放 `tmp/` 的独立任务目录，不覆盖旧输出，也不把旧 XSA 与新 bitstream 混用。

## 第三步：先验证 PL 配置下载

有了新 `.bit` 且确认板卡后：

1. 打开 Vivado `Hardware Manager`。
2. `Open Target > Auto Connect`，确认发现的目标器件是板上的 Zynq-7020。
3. 右键 FPGA 器件，选择 `Program Device`，指定刚构建的新 `.bit`。
4. 等待完成，检查硬件器件属性的 DONE 状态。当前工程没有 ILA，不需要凭空提供 `.ltx` 文件。

该步骤只证明配置下载，不会自动初始化完整 PS 或运行 ARM 应用。也可由下一步 Vitis 启动配置统一完成 FPGA 下载，避免分两套工具重复操作。

## 第四步：运行 PS 应用

使用本机 Vitis Unified IDE 2026.1。A 盘 Vitis 指南配套的是旧界面，里面 `Run As > Launch Hardware` 等菜单不能直接当作 2026.1 界面路径。

1. `File > New Component > Platform`，导入刚生成的固定硬件 XSA；创建处理器 `ps7_cortexa9_0`、操作系统 `standalone` 的平台/域并构建。核对 BSP 的标准输入输出使用 UART0。
2. 首次检查优先创建同一平台上的 Hello World 示例应用，构建 `.elf`。它只证明 PS/DDR/串口起步路径，不会处理 ECG。
3. 在应用的 Flow Navigator 打开 `Debug Settings`，创建启动配置并选择本地 JTAG/hw_server 目标连接。
4. 配置正确的新 bitstream，使用同一平台的 FSBL 或生成的 Tcl 做 `Board Initialization`，让启动流程完成所需复位、PS 初始化及 PL 配置。按实际配置使用 `Program Device`；应用部分选择 Cortex-A9 #0 和本次 `.elf`。初始化操作涉及实物，不能使用其他板卡的预设、FSBL 或 `ps7_init.tcl`。
5. 点击 Debug；若停在 `main()`，继续/Resume 运行。串口终端应显示应用打印的 Hello World。没有输出时先分开检查 COM/跳帽/波特率、程序是否暂停、PS 初始化与 BSP UART 选择。
6. 接着需要编写并构建 ECG 回放应用：写样本到 `0x43C00000`，读取 FIFO 状态、位置、RR、序号，完整读完后再弹出队首；定期记录丢弃计数并打印结果。目前该应用不存在。

未来回放程序的起步验收可包括：读取采样率寄存器 `0x43C00024`，期望当前配置为 360；读取积分窗口/不应期（120/200 ms）；送入固定数据，与软件/仿真同输入结果对照。访问 PL 前必须初始化 PS/时钟/复位，避免把 AXI 访问异常误判为算法错误。

## 断电后自动启动

后续把匹配硬件的 FSBL、新 bitstream 和 ECG 应用 ELF 组成 `BOOT.BIN`。SD 启动使用准备好的 FAT32 卡和对应启动模式；QSPI 固化还需要确认 Flash 器件、容量、布局、镜像与原有内容的保留方式。当前没有生成镜像，也没有格式化卡或写 Flash。

## 依据与验证边界

- A 盘 `2_文档教程/2_【正点原子】领航者ZYNQ之嵌入式Vitis开发指南V1.2.pdf`：第 2.5 节第 52–58 页（接线、P5、JTAG 模式、串口、Hello World 下载）；第 7.4–7.5 节第 155–159 页（固化原理与启动模式）。已阅读对应文字，并查看接线与启动表实际页面。
- A 盘 `2_文档教程/1_【正点原子】领航者ZYNQ之FPGA开发指南V3.4.pdf`：第 5.2.2 节第 115–116 页（BOOT_CFG）、第 5.2.7 节第 119 页（JTAG），查看实际原理图页面。
- [AMD UG908 2026.1：连接硬件目标](https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Opening-Hardware-Target-Connections)；[下载与 DONE 状态](https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Programming-the-Hardware-Device)。
- [AMD UG1400 2026.1：由 XSA 创建平台](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Creating-a-Platform-Component-from-XSA)；[创建应用](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Creating-an-Application-Component)；[启动配置](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Main-Page)；[Standalone 调试](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Debugging-Standalone-Application-Component)。

本次仅源码/文件与资料核查，没有连接目标、读写寄存器、配置 PL、初始化 PS、生成新版 bitstream/ELF、烧录 Flash 或修改 SD 卡。接线步骤属于匹配主目录手册时的操作依据，实物版本仍待确认。
