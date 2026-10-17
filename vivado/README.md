# Vivado工程

用Vivado2026.1直接打开ecg_edge/ecg_edge.xpr。工程只引用本仓库src/rtl和本目录的BD/wrapper；缓存、IP输出及综合结果由各自电脑生成，不复制原电脑tmp工作区。

克隆后首次打开可能出现“工程已移动”、IP输出目录/XCI缺失或器件模式下板卡预设为空的提示。打开ecg_system.bd后Vivado可从BD恢复IP定义；生成输出：

```tcl
generate_target all [get_files *ecg_system.bd]
update_compile_order -fileset sources_1
```

这些步骤不综合或下载。器件为xc7z020clg400-2，配置沿用正式build/build_navigator_ecg_system.tcl；具体实物修订仍需核对，不套用其他板卡。

若要在新目录重新生成文本工程，从仓库根运行：

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/share.tcl -tclargs tmp/share_new
```

不传输出目录时默认vivado/ecg_edge；已存在即停止，不覆盖当前工程。正式分享文件仅XPR、ecg_system.bd及sources_1/hdl/ecg_system_wrapper.v；原tmp工程和历史缓存保留，不当当前交付。完整综合/实现/bit/XSA流水线仍需另行验收。相关核查见[交接审查](../docs/records/checkout_20261017.md)。
