# 500Hz合成流上板核验

2026-10-20用户在本机Vitis运行ecg_stream后，在PC监视器停止并保存。本会话读取实际COM23记录核对；助手未操作板卡。范围为PS定时合成送样→AXI→原PL检测器→FIFO→USB_UART→PC接收保存，不包含真实ADS1292R采集、双向中转、滤波或CNN。

## 来源和匹配组合

- 原记录目录：tmp/pc_monitor_logs/20261020_220923_3a8c52db/，本次只读保留，不改写。前一目录220846是空端口启动失败，不混入成功结果。
- [完整串口原文](uart_stream_20261020_pass.log)：32163字节，SHA256见下方。正式副本与原件逐字节一致。
- H声明：ps-stream-2、SYNTH、QRS-ORIG-60、500Hz、scale未知、caps=0xD；会话0ed7e0d7f84649b300000000381426ca。重复H为同一会话每秒重发，不是重启。
- 用户使用的工作区：tmp/ecg_stream_500/vitis_workspace，配置ecg_stream_app_hw_1。核对正式main.c/stream.c/stream.h与工作区导入副本及manifest一致；ELF与匹配硬件哈希见本工作区build_manifest.json。日志只能显示会话声明，硬件镜像来源需结合本次操作和文件核对，不能单凭H证明下载镜像。

## 核验结果

| 项目 | 实际结果 |
| --- | --- |
| 样本 | 5003，序号/展开index为0..5002；逐值与先100零、每500点交替±20000单点脉冲一致 |
| 时间 | PC按500Hz生成逻辑时间0..10.004秒；不是ADC或示波器时间 |
| 事件 | 10个，seq=1..10，位置70+500*i（i=0..9）；RR首个0，其余500，名义心率60次/分 |
| 完整性 | wave_gap=0、event_gap=0、无解析错误；T报告event_drop/source_drop/tx_drop全0 |
| 结束 | END reason=completed samples=5003 events=10 tx_sample_drop=0 |
| 调度诊断 | queue_peak=165；max_late_ticks=349、timer_hz=333333343，仅软件调度入口观测，不是物理抖动测量 |
| PC关闭 | summary为stopped_by_user、串口opened/closed均true、无close_errors；板端在此之前已正常END |

本次有限合成流通过；B10/B11仅其合成回归子项可勾选。不能推导真实输入检测准确率、无线无丢样、持续压力通过或ECG-IN-1双向链路通过。首次事件70是当前原检测器的积分候选位置，不冒称准确R峰。

串口原文SHA256：

```text
8562d6376586c144818e8b0f2f98ddb1266341c65ad29e7eef2f7aaffc61112a
```
