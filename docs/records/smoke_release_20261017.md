# smoke交接、验收与发布记录

当前结论及不可变原始证据以[板上通过记录](smoke_board_validation_20261017.md)为准：用户返回的原检测器合成自检已通过。本文按实际先后合并原交接与发布过程；第一部分的“未上板”描述是制作候选包当时的状态，不是当前结论。本文不是新的板上测试报告，也不改变原日志、权重或镜像。

复跑和打包入口见[smoke自检与交接](../smoke_handoff.md)，当前匹配文件见[latest说明](../../releases/latest/README.md)。

## 一、交接包与离线重建（板上验收前）

用户要在其他电脑测试 smoke。本轮制作待验收工程包，不连接板卡、不写 Flash、不替换 releases/latest。**smoke 仍未上板测试**；本机重建不能替代接收方环境和实物验收。

### 交付与源码

- 当前可拷贝包：[ecg_smoke_kit_20261017_04.zip](../../tmp/ecg_smoke_kit_20261017_04.zip)，459862 字节，SHA256 `7279d3dc8e25caa63fb9de2226f8a16ea08ed21df8318ed963cd97ca35ff7f65`。
- 正式打包器：[board/package_ecg_smoke.py](../../board/package_ecg_smoke.py)，脚本模板在 board/smoke_handoff/，检查入口 [sim/check_smoke_handoff.py](../../sim/check_smoke_handoff.py)。使用说明见[交接教程](../smoke_handoff.md)。
- 包含 main.c、已构建 ELF、匹配 bit/XSA/ps7_init、Vitis 平台/应用构建入口、相对路径启动配置、XSDB JTAG 入口、预期串口及哈希清单。无 BOOT.BIN、数据集、工具安装包或完整缓存。
- 原 smoke main.c SHA256 `149fcf44ffff8f42f9d917a85f4b063803f2c87091b23e444fad284589e2216a`，ELF `2e573ba9a9244cd4a9ef0f5ce80eca8957e1b512594b9b9389fc616353285bf7`。其余组合及相对原始来源在包内 manifest.json；打包器固定检查五项已验证源文件哈希，变化即停止。

### 实际检查

本机 Windows、Vivado/Vitis 2026.1。完整包 ZIP CRC、15 个清单文件的 SHA256/字节数（加 manifest 共16个文件）、路径无越界或活动本机绝对引用、XSA 内嵌 bit 与独立 bit 逐字节一致，均通过。GUI 模板检查系统复位、重新配置 PL、PS 初始化和 post-init、Cortex-A9 核0、非入口停机；PowerShell/Tcl CheckOnly 均通过，不建立硬件连接。

从独立包路径 `tmp/ecg_smoke_kit_20261017_02` 创建平台和应用，构建到 `workspace` 成功，并生成启动配置。正式源码与导入副本一致；生成 ps7_init 与包内文件 SHA 相同。完整构建输出见[重建日志](smoke_handoff_build_20261017_simple.log)。BSP/FSBL 存在未使用参数、符号比较等工具生成警告，不把构建通过写成无警告。

重建 ELF 的总 SHA 不要求与旧路径产物相同。检查 ELF32 可分配文件节时发现 .text 不同，反汇编定位为末尾 GNU build-id 的20字节；仅归一化这一明确的构建标识后，所有可分配文件节的地址、长度、字节完全一致，其余执行代码/数据相同。证据：[节核对](../../tmp/smoke_handoff_checks/elf_normalized.json)、原始比较 elf_sections.json 及同目录反汇编。重建 ELF SHA256 `c3392dc00ff4abe12fc72989440460694c27e55b95cc13328249eb2ba5ef21ec`，包内仍保留原先冻结 ELF，没有悄悄替换。

离线 Tcl 替身检查将全部硬件入口替换为记录函数，解析真实 ps7_init 定义，再核对 connect→选核→系统复位→配置PL→PS初始化→post-init→选核→下载ELF→运行→断开顺序。见[替身输出](smoke_handoff_mock_20261017.log)；这是调用顺序检查，不是 JTAG/板卡执行。

### 失败与修正

1. 旧 XSCT 在2026.1直接提示禁用，改为本机实际可用的 Tcl XSDB。不能只因 xsct.bat 文件存在而声称可运行。
2. Vitis 启动批处理剥掉脚本路径引号，带空格绝对脚本名被截断，改为在包目录执行相对脚本路径。随后发现 Vitis 平台本身拒绝带空格工作区；生成入口明确检查无空格英文路径并提前报错。带空格失败日志仍保留在本目录 smoke_handoff_build_20261017.log 与 smoke_handoff_build_20261017_02_retry.log。
3. Vitis/XSDB 批处理有失败但返回0的情况，生成工作区入口额外检查最终 ELF 和 launch.json，JTAG 入口核对脚本启动完成标记；启动完成仍不等于 smoke 通过，最终以 UART 为准。受限环境构建未继续的进程已中断；使用经批准的非受限本地构建验证，无安装或权限修改。
4. 受限环境 objcopy 因系统 DLL 重定位无法启动；未修改工具，改用独立 ELF 节读取，并通过获准的只读 objdump 定位 build-id，保留最初不相同的检查结论及修正依据。
5. Tcl 替身最初 source 包装没有保留调用作用域，导致 argc 不存在；修正为 uplevel 后通过，未改真实 JTAG 脚本来适配测试替身。

失败包01/02、解压迁移尝试和工作区均保留 tmp，不删除。03通过检查后补强了批处理假成功判断，最终04是交付入口，仍为候选；本轮未运行 Git、Computer Use、Flash、安装依赖或修改受保护 README/资料索引。

### 接收方验收

需要匹配的领航者V2/7020、可靠供电、JTAG、USB_UART和自行安装的工具/驱动。实际核心板/底板修订仍须核对。只接一块目标板；串口用接收方实际 COM、115200 8N1 无流控。运行每次必须重新配置 PL。最终必须出现 `PASS ECG_SMOKE failures=0` 且中间无 FAIL，并保存从 BEGIN 起完整串口文本与工具/板卡版本。

未实测接收方安装、GUI点击、JTAG连接或板上程序；不保证其他工具版本的 API/XSA 兼容。此项只验证原检测器的受控合成样本、寄存器和FIFO，不验证候选QRS、CNN、INT8、AFE/ADC或疾病诊断。

### 文档复核

全库检查36份Markdown、211个链接，受保护根README、资料索引、latest说明/清单及11项QRS冻结哈希保持一致。本轮新增/修改文档链接没有错误；全库检查未完全通过，唯一报错是未修改的 docs/HDMI.md 使用 `project_plan.md#L181` 行号锚点，校验器不将其识别为标题锚点。未扩大范围修改该文件或覆盖其他成员改动。证据位于 tmp/doc_maintenance_20261016/verification.json。

## 二、发布与归档（收到通过证据后）

### 授权与交付

用户要求归档旧release、latest换为这次跑通的smoke、合并相关新功能，先不提交推送。本轮仅本地更新文件，不操作索引、提交、推送、板卡或Flash。

当前版本为`20261017-ecg-smoke-jtag-v1`，入口[releases/latest/README.md](../../releases/latest/README.md)。旧`20261013-hello-world-qspi-v1`完整移至本机`releases/history/20261013-hello-world-qspi-v1/`，8个文件移动前后逐文件SHA256一致，未删除或改写旧BIF/清单/README。归档中旧相对文档路径仍是历史字节，当前文档入口以本次记录及docs为准。

新版采用返回包的hardware/prebuilt/board/src层级；manifest.json供运行脚本核验，artifacts.json记录来源、哈希及验收范围。没有BOOT.BIN、FSBL、boot.bif或hello_world.elf，不能用JTAG通过代替QSPI掉电启动验收。

### 来源与合并

从用户返回ZIP提取原manifest中15个载荷，逐文件字节数和SHA256核验通过。返回包原manifest、报告和UART仍原样留[板上记录](smoke_board_validation_20261017.md)。发布的main.c、ELF、bit、XSA及ps7_init五项核心文件与该通过包一致；原始报告COM3及工具盘符仅对应对方机器，不固化为共用配置。

当前正式main.c及两份RTL与历史匹配；没有新的PS/RTL业务功能需要混入已验收镜像。硬件构建Tcl与旧清单的SHA不同，找到SHA等于旧清单的备份并逐行比较，差异仅两处RTL位置从rtl/调整为src/rtl/，未改逻辑/PS参数。没有为本次发布重新综合实现，不能声称新构建通过。

新增功能来自返回包的`board/capture_uart.ps1`：合并到正式`board/smoke_handoff/`并收入latest，原始返回脚本副本保留tmp/backup/smoke_release_20261017/。针对跨电脑和日志保留做了限定修改：端口与日志路径必须显式指定，115200/8N1/无流控，被动读取不发送命令；CreateNew拒绝覆盖已有日志；超时/FAIL报错并保留输出，兼容返回日志CR换行；CheckOnly不打开串口或创建文件。上述改动只完成离线检查，未在实物重新验收，不把新辅助脚本标成已上板通过。

JTAG复位/PL配置/PS初始化/运行脚本与通过包相同；Vitis构建脚本仅更新默认XSA路径，工作区创建器本来就显式设置包内XSA环境变量。正式打包器改从latest/hardware与prebuilt获取匹配文件，不依赖原本机tmp工作区，并将capture脚本加入后续候选包。

### 实际检查

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

### 验收边界

已接受的是用户实际板上报告及UART证明的PS→AXI→原检测器→FIFO合成输入通过。本轮不复跑实物，不合入尚未合格的分类模型，不验证ADS1292R、真实AFE/ADC、软件候选峰RTL、CNN/INT8/PL推理或QSPI固化。JTAG掉电后需重新下载；旧Hello World/QSPI仅作历史保留。当前授权不包含远端发布。

## 三、本次文档合并范围

2026-10-17合并两份过程记录，原交接记录原字节归档tmp/history/smoke_docs_20261017_01/smoke_handoff_20261017.md；原文档副本和哈希在tmp/backup/merge_smoke_docs_20261017_01。两部分正文只调整标题层级，失败过程、旧状态与原始证据路径保留，不覆盖历史结论。板上证据及其所引用的原始UART/报告原字节不变。后续新验收必须另记日期、输入、版本及实际结果，不能把此合并视为重新通过板上测试。
