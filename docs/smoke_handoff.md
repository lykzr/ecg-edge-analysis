# 独立PL自检

本自检只验证 PS→AXI→QRS候选检测器→事件FIFO，不验证当前ARM检测算法、真实输入或分类。使用 releases/latest/smoke/ 的匹配硬件、ELF及 run_smoke.tcl，不与 runtime500/、bridge/ 混用。

从项目根执行（实际工具安装路径替换占位值）：

```powershell
& '<Vitis>/bin/xsdb.bat' releases/latest/smoke/run_smoke.tcl --check-only
```

先按[下载教程](download_guide.md)核对板卡、JTAG拨码、串口115200/8N1与供电。--check-only仅检查文件；确认只连接目标板卡后，去掉该参数才会实际复位并下载。脚本可选参数是硬件服务器URL，不是下载器序列号；串口完整出现 PASS ECG_SMOKE failures=0 且无FAIL才算自检通过。启动工具成功不能代替该判据。该自检不写Flash。

