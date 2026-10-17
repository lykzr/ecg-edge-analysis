# 2026-10-17 smoke发布替换与新增辅助功能合并

## 授权与交付

用户要求归档旧release、latest换为这次跑通的smoke、合并相关新功能，先不提交推送。本轮仅本地更新文件，不操作索引、提交、推送、板卡或Flash。

当前版本为`20261017-ecg-smoke-jtag-v1`，入口[releases/latest/README.md](../../releases/latest/README.md)。旧`20261013-hello-world-qspi-v1`完整移至本机`releases/history/20261013-hello-world-qspi-v1/`，8个文件移动前后逐文件SHA256一致，未删除或改写旧BIF/清单/README。归档中旧相对文档路径仍是历史字节，当前文档入口以本次记录及docs为准。

新版采用返回包的hardware/prebuilt/board/src层级；manifest.json供运行脚本核验，artifacts.json记录来源、哈希及验收范围。没有BOOT.BIN、FSBL、boot.bif或hello_world.elf，不能用JTAG通过代替QSPI掉电启动验收。

## 来源与合并

从用户返回ZIP提取原manifest中15个载荷，逐文件字节数和SHA256核验通过。返回包原manifest、报告和UART仍原样留[板上记录](smoke_board_validation_20261017.md)。发布的main.c、ELF、bit、XSA及ps7_init五项核心文件与该通过包一致；原始报告COM3及工具盘符仅对应对方机器，不固化为共用配置。

当前正式main.c及两份RTL与历史匹配；没有新的PS/RTL业务功能需要混入已验收镜像。硬件构建Tcl与旧清单的SHA不同，找到SHA等于旧清单的备份并逐行比较，差异仅两处RTL位置从rtl/调整为src/rtl/，未改逻辑/PS参数。没有为本次发布重新综合实现，不能声称新构建通过。

新增功能来自返回包的`board/capture_uart.ps1`：合并到正式`board/smoke_handoff/`并收入latest，原始返回脚本副本保留tmp/backup/smoke_release_20261017/。针对跨电脑和日志保留做了限定修改：端口与日志路径必须显式指定，115200/8N1/无流控，被动读取不发送命令；CreateNew拒绝覆盖已有日志；超时/FAIL报错并保留输出，兼容返回日志CR换行；CheckOnly不打开串口或创建文件。上述改动只完成离线检查，未在实物重新验收，不把新辅助脚本标成已上板通过。

JTAG复位/PL配置/PS初始化/运行脚本与通过包相同；Vitis构建脚本仅更新默认XSA路径，工作区创建器本来就显式设置包内XSA环境变量。正式打包器改从latest/hardware与prebuilt获取匹配文件，不依赖原本机tmp工作区，并将capture脚本加入后续候选包。

## 实际检查

- 替换前在tmp/smoke_release_stage_20261017建立新交付并检查，旧版目标不存在才移动；替换前再次核对旧latest快照，避免覆盖并发改动。旧8文件归档原字节一致，根README和docs/materials_review保持不变。
- `python -B sim/check_smoke_release.py`通过：16个载荷、manifest/artifacts完整哈希、正式源码/辅助脚本同步、XSA内嵌bit一致、ARM ELF头、运行配置、用户UART关键行和源文件/证据哈希通过。没有连接实物。
- latest的PowerShell run_smoke.ps1 CheckOnly通过，只核验清单；AMD XSDB执行run_smoke.tcl --check-only通过，均未连接板卡。
- 新采集脚本PowerShell语法和CheckOnly通过，确认无串口打开/日志创建；使用现有哨兵日志测试，脚本拒绝覆盖且原内容保持一致。尚未测试实际串口超时/FAIL分支或实物采集。
- 正式打包器成功重新生成tmp/ecg_smoke_release_repack_20261017.zip，离线ZIP、全部载荷哈希、相对启动路径、XSA/bit及GUI复位配置检查通过。该新候选包manifest保留NOT_TESTED，不自动产生新板上成绩，也不自动替换latest。
- .gitignore按当前明确交付逐文件放行，18个latest文件可跟踪；history、运行工作区和非清单文件仍忽略。没有Git暂存、提交、推送或清理。
- 受影响Python语法及scoped git diff --check通过。Windows换行提示属于既有Git转换提示，未通过Git重写文件。

可复现命令：

```powershell
python -B sim/check_smoke_release.py
python -B board/package_ecg_smoke.py --output-dir tmp/smoke_repack_new
python -B sim/check_smoke_handoff.py tmp/smoke_repack_new.zip
powershell -NoProfile -ExecutionPolicy Bypass -File releases/latest/board/run_smoke.ps1 -VitisBin '<Vitis安装目录>/bin' -CheckOnly
```

移动映射/旧文件哈希/核心文件来源：tmp/smoke_release_update_20261017.json。Git放行检查：tmp/smoke_release_git_check_20261017.json。文档检查：tmp/smoke_release_doc_20261017/verification.json及[原始日志](smoke_release_doc_check_20261017.log)。全库另外保留4处既有HDMI.md缺失链接，非本次发布文件，未恢复他人文档；当前发布链接会在记录创建后重新检查，不声称全库无错误。

## 验收边界

已接受的是用户实际板上报告及UART证明的PS→AXI→原检测器→FIFO合成输入通过。本轮不复跑实物，不合入尚未合格的分类模型，不验证ADS1292R、真实AFE/ADC、软件候选峰RTL、CNN/INT8/PL推理或QSPI固化。JTAG掉电后需重新下载；旧Hello World/QSPI仅作历史保留。当前授权不包含远端发布。
