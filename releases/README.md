# 发布与历史归档

当前交付为[20261101会话复用JTAG/QSPI包](latest/README.md)，构建ID为36e807fd28c440f5。正常完成或停止保存后可直接新建会话；协议或串口错误仍停止。下载、烧录和重建按包内说明及[下载教程](../docs/download_guide.md)。

latest仅包含匹配产物和清单：runtime500/为500Hz ARM检测/切拍的bit、XSA、初始化、ELF及JTAG入口；qspi/为匹配BOOT.BIN、FSBL、BIF及编程/复位脚本；smoke/和bridge/分别保留独立基础自检与旧legacy500回归组合。源码、教程和验收证据在仓库中，不把工具缓存复制进发布包。各组件禁止交叉替换。

manifest.json列出全部文件字节数和SHA256，artifacts.json记录构建来源、源码哈希及分阶段证据。检查命令：

```powershell
python -B sim/check_system_release.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/qspi/program_qspi.ps1 -CheckOnly
```

默认检查不连接板卡。实际编程必须显式-Program；另一块板卡仍须分别验收编程、校验、系统复位及彻底断电启动。有限数字连续会话不代表无线长时、拔插恢复、界面人工操作、分类精度或最终CNN/INT8/FPGA推理完成。

旧版32份文件完整保留在history/20261025-runtime500-qspi-v1/，原字节与归档前逐项哈希一致；其他历史目录继续保留，不覆盖、不删除。替换latest前须校验现有文件、确认目标在工程内且历史版本不存在；先生成并检查候选，再归档替换。历史默认忽略，latest仅明确放行清单文件；本地更新不代表提交、推送或上传。

本次验收与发布记录见[当前实现与缺项](../report/report.md)及[发布收据](../data/results/session_reuse_release_20261101.json)。
