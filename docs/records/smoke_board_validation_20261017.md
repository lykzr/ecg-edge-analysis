# 2026-10-17 ECG smoke 板上通过证据

结论：**PASS ECG_SMOKE failures=0**。依据为用户提供的实际开发板运行报告和完整串口文件；本会话复核附件内容，没有自行再次操作板卡。

## 环境与覆盖

报告记录领航者V2/xc7z020、Digilent JTAG-HS1、Vivado/Vitis2026.1，串口COM3/115200/8N1/无流控；工程运行在另一电脑的D:/ecg_smoke_kit_20261017_04。具体核心板/底板修订仍未由本次报告确定。报告中的工具安装盘符只属于该机器，其他成员替换实际路径。

JTAG流程复位系统、配置PL、PS初始化并加载原ecg_smoke.elf。合成脉冲通过配置、零输入、事件字段/出队、FIFO溢出及清空/溢出标志检查。四事件index为79/439/799/1159，RR为0/360/360/360；溢出queued=8、total=16、dropped=4，最终failures=0。

## 保留的原始证据

- [用户原始运行报告](smoke_board_20261017/run_result_original.md)，原字节保存。
- [完整UART日志](smoke_board_20261017/uart_smoke_pass.log)，原字节保存。
- [JTAG启动日志](smoke_board_20261017/jtag_smoke_pass.log)；它本身只表明启动提示，不能单独证明自检通过。
- [原工程包清单](smoke_board_20261017/kit_manifest_original.json)及[本次核验摘要](smoke_board_20261017/verification.json)。

返回ZIP SHA256为d2af841f98201043c06d9d3e875507099fe35b21f3ddb788050b08cd7a42525e。原manifest列出15个载荷文件，逐文件长度和SHA256全部匹配；manifest本身另计，即报告所说原16文件。报告、日志和capture脚本属于返回时的附加内容，不修改原清单来声称它们原已发布。

UART原字节SHA256为268d65ed0fcb2b7d7a0fed2464a6fe97dc98ccf977fd8f8d8c0f10f6e57b13ff。按非空行核验，expected_uart.txt全部关键行原顺序一致，无FAIL开头行。首次使用全日志等长比较发现多出正常提示`Synthetic samples; no ADC; no clinical accuracy claim.`；改为明确只允许这一条已知提示、其余行严格相等，未删除原始日志或放宽事件数值。

## 验证边界与后续

本次证明PS→AXI→**现有原检测器**→事件FIFO合成输入链路在报告所述板上运行通过；不证明软件候选峰算法已移植RTL，不代表公开ECG端到端检测、CNN、INT8或FPGA分类推理通过。ADS1292R/真实AFE/ADC/人体输入尚未验证。

本次为临时JTAG运行，未写QSPI，掉电后需重新下载；不沿用此前Hello World掉电运行成绩代替ECG smoke固化验收。原目录送回收站的描述仅为对方报告内容，本会话未操作其目录或回收站。复跑方法见[跨电脑smoke说明](../smoke_handoff.md)。
