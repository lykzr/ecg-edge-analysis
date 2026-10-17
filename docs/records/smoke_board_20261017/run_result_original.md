# ECG smoke 板上运行记录

日期：2026-10-17（Asia/Shanghai）。

结果：**PASS ECG_SMOKE failures=0**。

- 目标：正点原子领航者 V2 / xc7z020。
- 下载器：Digilent JTAG-HS1；已识别 ARM DAP、xc7z020 和两个 Cortex-A9 核。
- 工具：本机 AMD Vivado/Vitis 2026.1。
- 运行目录：D:\ecg_smoke_kit_20261017_04。
- 串口：COM3，115200，8N1，无流控。
- 方式：使用包内原始 board/run_smoke.ps1，临时 JTAG 复位系统、配置 PL、初始化 PS、下载并运行 prebuilt/ecg_smoke.elf。
- 包内 manifest 文件 SHA256 校验通过；原目录全部 16 个文件与 D 盘副本一致。
- 串口关键行与 expected_uart.txt 逐行、按顺序比对通过；没有以 FAIL 开始的日志行。
- 通过项：CONFIG、ZERO_INPUT、EVENT_FIELDS_AND_POP、FIFO_OVERFLOW、FIFO_DRAIN_AND_OVERFLOW_CLEAR。
- FIFO 溢出结果：queued=8，total=16，dropped=4。
- 日志：logs/uart_smoke_20261017_pass.log、logs/jtag_smoke_20261017_pass.log。

## 复跑

1. 保持匹配电源、PS UART 和 JTAG 连接，BOOT_CFG 为 JTAG（两个 ON）。
2. 使用 board/capture_uart.ps1 打开本机实际 COM 口，或使用串口终端保存日志。
3. 确保本机 hw_server 已运行，然后在此英文目录执行 README 中的 run_smoke.ps1 命令。本机 VitisBin 是 D:\AMDXilinx\2026.1\Vitis\bin。
4. 每次完整重跑都重新配置 PL；以完整串口日志及最后的 PASS ECG_SMOKE failures=0 判断通过。

本次使用合成脉冲，验证 PS → AXI → 原检测器 → 事件 FIFO，不涉及 ADS1292R、人体心电输入、疾病诊断或临床准确率；未烧写 QSPI，掉电不保留本次 JTAG 配置。

备注：从 .codex 和 AppData 目录运行时，本机 AMD Tcl 对路径规范化出现丢失目录名的问题；最终在 D 盘根目录使用未修改的原始运行脚本成功运行。

原工程目录 D:\虚拟c盘\ecg_smoke_kit_20261017_04 已在逐文件校验后送入 Windows 回收站。后续使用 D:\ecg_smoke_kit_20261017_04。
