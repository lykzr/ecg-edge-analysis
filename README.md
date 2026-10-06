# 基于 Zynq-7020 的心电边缘分析项目

这是项目的第一版 RTL 工程。检测算法模块本身可参数化；当前 Vivado 工程按黑金 AC7020（Zynq-7020）配置。模块用采样差分、滑动积分、自适应阈值和不应期产生 QRS 候选点。

## 当前实现范围

- 输入：带有效标志的有符号心电采样。
- 输出：QRS 候选脉冲、估计采样位置、以采样点数表示的 RR 间期。
- 这只是算法基线，不是临床级心电分析器。当前还没有模拟前端、ADC 接口、信号质量分类、波形显示或心律分类。
- 当前工程目标板按黑金 AC7020 配置，器件为 `xc7z020clg400-2`。PS7 与 ECG AXI-Lite Block Design 已配置；Vitis 应用、采样率、输入幅值和 ADC 接口仍需后续确认。

## 用 Vivado 创建 RTL 工程

确认板卡上标注的准确器件型号后，在工作区根目录打开 PowerShell，运行：

```powershell
& '<Vivado安装目录>/Vivado/bin/vivado.bat' -mode batch -source ecg_edge/scripts/create_rtl_project.tcl -tclargs <Vivado器件完整型号>
```

将 `<Vivado安装目录>` 替换成当前电脑上的实际安装目录。

脚本会创建 `ecg_edge/build/ecg_edge`。如果目标工程目录已经存在，脚本会停止，不会覆盖。该脚本只创建 RTL 工程并添加源文件；它不会综合、仿真或生成 bitstream。

初次验证建议使用 JTAG 临时下载 bitstream。确认板卡的启动开关、SD 卡和 Flash 接线前，先不要写入 SD/QSPI 启动镜像。

## 一次性配置 AC7020 + PS7 + ECG AXI-Lite

Vivado 内置板级预设没有 AC7020，因此不要选择 ZC702、ZC706 或 ZedBoard。完整配置脚本按 AC7020 手册和随附教程工程的参数设置 PS7：33.333 MHz 输入时钟、32 位 DDR3、533.333 MHz、UART1 使用 MIO48/49，并启用 100 MHz FCLK0 和 PS 的 M_AXI_GP0。

配置完成后，PS 通过 AXI-Lite 写入 ECG 采样并读取检测结果。寄存器基地址为 `0x43C00000`：

| 偏移 | 访问 | 含义 |
|---|---|---|
| `0x00` | 写 | 低 16 位为一个有符号 ECG 采样；每次成功写入送入一个采样 |
| `0x04` | 读/写 | bit0 为 QRS 待处理标志；写 bit0=1 清除 |
| `0x08` | 读 | QRS 候选位置（采样点） |
| `0x0C` | 读 | RR 间期（采样点） |
| `0x10` | 读 | 滑动积分能量 |
| `0x14` | 读 | 自适应检测阈值 |

在 Vivado 打开当前工程，关闭 PS7 参数窗口并回到 `ecg_system` Block Design，然后在 Tcl Console 执行：

```tcl
set project_root [file normalize [file join [get_property DIRECTORY [current_project]] .. ..]]
source [file join $project_root scripts build_ac7020_ecg_system.tcl]
```

脚本会添加 ECG AXI-Lite RTL、设置 PS7、连接 AXI/时钟/复位、分配地址、验证并保存 Block Design，生成 HDL wrapper 并准备 IP 输出文件。该脚本不启动综合、实现、bitstream 生成或烧录。实际采集仍需后续确认 ADC/模拟前端和板卡接口。

## 后续开发步骤

1. 确认板卡型号和 Vivado 器件完整型号。
2. 确认心电模拟前端（AFE）、ADC 和采样格式。
3. 编写软件参考算法和公开心电记录回放程序。
4. 添加自检仿真向量，并逐项比较 RTL 与软件参考结果。
5. 加入信号质量评估，并测试不同噪声条件下的效果。
6. 添加 PS/Vitis 控制和显示程序，再补板卡专用约束与启动文件。

## 算法参数

`SAMPLE_RATE_HZ`（采样率）、`INTEGRATION_MS`（积分窗口时长）、`REFRACTORY_MS`（不应期）和初始自适应阈值均为模块参数。当前默认值只是开发占位值；确定采样率和输入幅值后，需用带标注的心电记录重新调整。输出事件位置按积分窗口的一半做了粗略回移，仍需与参考标注对比验证。

## 验证状态

Vivado 2026.1 已完成 Block Design 验证、综合和实现。尚未完成算法仿真、上板验证或心电输入验证；没有实测结果前，不应把默认参数或估计指标写成实验结论。
