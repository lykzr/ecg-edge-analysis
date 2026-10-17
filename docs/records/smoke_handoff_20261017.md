# 2026-10-17：跨电脑 smoke 工程交接检查

用户要在其他电脑测试 smoke。本轮制作待验收工程包，不连接板卡、不写 Flash、不替换 releases/latest。**smoke 仍未上板测试**；本机重建不能替代接收方环境和实物验收。

## 交付与源码

- 当前可拷贝包：[ecg_smoke_kit_20261017_04.zip](../../tmp/ecg_smoke_kit_20261017_04.zip)，459862 字节，SHA256 `7279d3dc8e25caa63fb9de2226f8a16ea08ed21df8318ed963cd97ca35ff7f65`。
- 正式打包器：[board/package_ecg_smoke.py](../../board/package_ecg_smoke.py)，脚本模板在 board/smoke_handoff/，检查入口 [sim/check_smoke_handoff.py](../../sim/check_smoke_handoff.py)。使用说明见[交接教程](../smoke_handoff.md)。
- 包含 main.c、已构建 ELF、匹配 bit/XSA/ps7_init、Vitis 平台/应用构建入口、相对路径启动配置、XSDB JTAG 入口、预期串口及哈希清单。无 BOOT.BIN、数据集、工具安装包或完整缓存。
- 原 smoke main.c SHA256 `149fcf44ffff8f42f9d917a85f4b063803f2c87091b23e444fad284589e2216a`，ELF `2e573ba9a9244cd4a9ef0f5ce80eca8957e1b512594b9b9389fc616353285bf7`。其余组合及相对原始来源在包内 manifest.json；打包器固定检查五项已验证源文件哈希，变化即停止。

## 实际检查

本机 Windows、Vivado/Vitis 2026.1。完整包 ZIP CRC、15 个清单文件的 SHA256/字节数（加 manifest 共16个文件）、路径无越界或活动本机绝对引用、XSA 内嵌 bit 与独立 bit 逐字节一致，均通过。GUI 模板检查系统复位、重新配置 PL、PS 初始化和 post-init、Cortex-A9 核0、非入口停机；PowerShell/Tcl CheckOnly 均通过，不建立硬件连接。

从独立包路径 `tmp/ecg_smoke_kit_20261017_02` 创建平台和应用，构建到 `workspace` 成功，并生成启动配置。正式源码与导入副本一致；生成 ps7_init 与包内文件 SHA 相同。完整构建输出见[重建日志](smoke_handoff_build_20261017_simple.log)。BSP/FSBL 存在未使用参数、符号比较等工具生成警告，不把构建通过写成无警告。

重建 ELF 的总 SHA 不要求与旧路径产物相同。检查 ELF32 可分配文件节时发现 .text 不同，反汇编定位为末尾 GNU build-id 的20字节；仅归一化这一明确的构建标识后，所有可分配文件节的地址、长度、字节完全一致，其余执行代码/数据相同。证据：[节核对](../../tmp/smoke_handoff_checks/elf_normalized.json)、原始比较 elf_sections.json 及同目录反汇编。重建 ELF SHA256 `c3392dc00ff4abe12fc72989440460694c27e55b95cc13328249eb2ba5ef21ec`，包内仍保留原先冻结 ELF，没有悄悄替换。

离线 Tcl 替身检查将全部硬件入口替换为记录函数，解析真实 ps7_init 定义，再核对 connect→选核→系统复位→配置PL→PS初始化→post-init→选核→下载ELF→运行→断开顺序。见[替身输出](smoke_handoff_mock_20261017.log)；这是调用顺序检查，不是 JTAG/板卡执行。

## 失败与修正

1. 旧 XSCT 在2026.1直接提示禁用，改为本机实际可用的 Tcl XSDB。不能只因 xsct.bat 文件存在而声称可运行。
2. Vitis 启动批处理剥掉脚本路径引号，带空格绝对脚本名被截断，改为在包目录执行相对脚本路径。随后发现 Vitis 平台本身拒绝带空格工作区；生成入口明确检查无空格英文路径并提前报错。带空格失败日志仍保留在本目录 smoke_handoff_build_20261017.log 与 smoke_handoff_build_20261017_02_retry.log。
3. Vitis/XSDB 批处理有失败但返回0的情况，生成工作区入口额外检查最终 ELF 和 launch.json，JTAG 入口核对脚本启动完成标记；启动完成仍不等于 smoke 通过，最终以 UART 为准。受限环境构建未继续的进程已中断；使用经批准的非受限本地构建验证，无安装或权限修改。
4. 受限环境 objcopy 因系统 DLL 重定位无法启动；未修改工具，改用独立 ELF 节读取，并通过获准的只读 objdump 定位 build-id，保留最初不相同的检查结论及修正依据。
5. Tcl 替身最初 source 包装没有保留调用作用域，导致 argc 不存在；修正为 uplevel 后通过，未改真实 JTAG 脚本来适配测试替身。

失败包01/02、解压迁移尝试和工作区均保留 tmp，不删除。03通过检查后补强了批处理假成功判断，最终04是交付入口，仍为候选；本轮未运行 Git、Computer Use、Flash、安装依赖或修改受保护 README/资料索引。

## 接收方验收

需要匹配的领航者V2/7020、可靠供电、JTAG、USB_UART和自行安装的工具/驱动。实际核心板/底板修订仍须核对。只接一块目标板；串口用接收方实际 COM、115200 8N1 无流控。运行每次必须重新配置 PL。最终必须出现 `PASS ECG_SMOKE failures=0` 且中间无 FAIL，并保存从 BEGIN 起完整串口文本与工具/板卡版本。

未实测接收方安装、GUI点击、JTAG连接或板上程序；不保证其他工具版本的 API/XSA 兼容。此项只验证原检测器的受控合成样本、寄存器和FIFO，不验证候选QRS、CNN、INT8、AFE/ADC或疾病诊断。

## 文档复核

全库检查36份Markdown、211个链接，受保护根README、资料索引、latest说明/清单及11项QRS冻结哈希保持一致。本轮新增/修改文档链接没有错误；全库检查未完全通过，唯一报错是未修改的 docs/HDMI.md 使用 `project_plan.md#L181` 行号锚点，校验器不将其识别为标题锚点。未扩大范围修改该文件或覆盖其他成员改动。证据位于 tmp/doc_maintenance_20261016/verification.json。
