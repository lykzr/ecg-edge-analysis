# 跨电脑 smoke 工程交接

适用于把原工程的 PS/AXI/FIFO 自检交给另一台电脑运行。交接包包含成套 XSA/bit/ps7_init、已编译 ELF、PS 源码、Vitis 工作区生成器和 JTAG 运行脚本。接收方自行安装 AMD 工具与驱动；本机路径、COM 号和缓存不作为依赖。

## 制作与核对

在项目根目录使用 Python 3 标准库：

```powershell
python -B board/package_ecg_smoke.py --output-dir tmp/ecg_smoke_kit_new
python -B sim/check_smoke_handoff.py tmp/ecg_smoke_kit_new.zip
```

已有目标即停止，避免覆盖历史；输出限定 tmp。打包器钉住所验证的 main.c/ELF/bit/XSA/ps7_init 哈希，正式源码或产物变化时停止，需要重新构建验证后再更新冻结组合。包内 manifest 记录相对来源、字节数及 SHA256。此包是待验收候选，不替换 releases/latest。

## 接收方操作

完整解压到无空格英文目录，例如 `D:\ecg_smoke_kit`。先读包内 README，按其连接 JTAG、供电和 USB_UART；串口使用实际 COM、115200 8N1 无流控。

最短路线：使用 `board/run_smoke.ps1` 运行已有 ELF；GUI 路线：使用 `board/create_workspace.ps1` 在本机生成并构建 workspace，然后 Vitis Set Workspace，选择 ecg_smoke → Run。两种入口均通过 `-VitisBin` 指定接收方安装目录，完整命令在包内说明。默认使用 2026.1；旧版本重建兼容性另行核对。

工作区必须在接收方创建；不要从本机直接拷贝已生成 workspace，因为平台和构建缓存有本机绝对路径。创建后不再移动工作区。每次运行都复位系统并重新配置 PL，避免旧 FIFO 状态影响结果。

最后 `PASS ECG_SMOKE failures=0` 且中间无 FAIL 才算通过，保存完整 BEGIN 到结尾的串口文本、工具版本、板卡版本与报错。JTAG 临时运行不写 Flash，不需要 ECG 真实输入。验证内容、完整预期输出及局限见[下载教程](download_guide.md)。

实际迁移构建检查和未上板边界见[交接记录](records/smoke_handoff_20261017.md)。

当前验收：用户2026-10-17返回实际开发板报告及UART，合成输入自检PASS ECG_SMOKE failures=0，见[上板证据](records/smoke_board_validation_20261017.md)。旧交接记录的未上板是此前快照；本次仍未验证ADS1292R实采或QSPI掉电启动。

当前正式交付在[releases/latest](../releases/latest/README.md)，已纳入返回包新增的串口采集脚本；运行报告/日志仍集中docs/records。重新生成候选ZIP不会自动替换latest或继承新的板上结果，打包器现从latest的匹配hardware/prebuilt取文件，不依赖原电脑工作区。
