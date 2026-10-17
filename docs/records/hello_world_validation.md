# 验证记录摘要

日期：2026-10-13。来源：本机工具输出及用户在当前会话提供的板上日志，非助手独立操作硬件。

- BD 验证、综合、实现、bitstream 与 XSA 导出通过。WNS +0.329 ns、WHS +0.057 ns、WPWS +3.870 ns，DRC 无违规。
- 平台、FSBL、Hello World 构建通过，FSBL BSP 包含单颗 QSPI 实例。Bootgen 生成并读取镜像头成功；输入顺序 FSBL → bitstream → 应用 ELF。
- 用户首次烧录：擦除成功后，在安装目录创建临时文件失败。随后用户从项目可写目录运行 Program Flash；一次 Ctrl+C 中断后重试，提供 `Verify Operation successful.`。不是只凭擦除成功判断烧录成功。
- 用户 COM14/115200 复位后输出如下。日志中连着出现两组打印，此处保留原提供的内容：

```text
Opened with baud rate: 115200
Hello World
Successfully ran Hello World applicationHello World
Successfully ran Hello World application
```

完整断电再上电测试没有从最后反馈中单独确认；ECG 接口读写、样本回放、算法准确率、AFE/ADC、人体采集均未验证。用户已授权归档当前版本，按上述实际验证范围发布，不扩大为完整功能或掉电验收通过。
