# 可复现硬件构建入口

本目录只保存正式Tcl脚本，工具工程、缓存和报告写入tmp/。

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/create_rtl_project.tcl -tclargs xc7z020clg400-2
```

默认创建tmp/vivado/ecg_edge，已有目录即停止。可在器件参数之后另给一个新的输出目录，用于独立验证，不覆盖活动工程。此入口只创建并验证BD及生成输出，不自动综合、实现或生成bitstream。

已有工程可执行build/build_navigator_ecg_system.tcl更新；迁移前生成的工程可能引用旧src路径，应从新入口重新生成，不能将旧缓存作为从零复现证明。完整综合/实现/导出的一键流水线、资源性能汇总与干净环境复现仍列在计划中。

初级组PYNQ为推荐，非本工程当前依赖。实际板卡领航者V2，具体修订仍待实物核对；不可把当前配置当其他板卡预设。

旧AC7020名称兼容入口已归档tmp/history/training_handoff_20261017/build/；正式入口仅使用领航者脚本，不再以旧板卡名引导新成员。

## 直接打开的共享工程

[正式Vivado工程](../vivado/ecg_edge/ecg_edge.xpr)与必要BD/wrapper随仓库交接，使用方法见[vivado说明](../vivado/README.md)。从空目录重新生成使用share.tcl，可另传新输出目录；它调用既有领航者构建配置，不综合、不下载。extract_gqrs_core.py是正式算法生成器，按固定WFDB版本复现GQRS派生核心到新目录，不覆盖已有源文件/许可。

## 独立500Hz流式候选

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/stream_500.tcl
```

该入口复用领航者构建脚本并显式设SAMPLE_RATE_HZ=500，在新的tmp/ecg_stream_500生成工程、综合/实现报告、bit/XSA及匹配ps7_init。可另传一个新的输出根目录；自定义目录后Vitis构建须显式指定三项匹配文件路径。它不更改正式360Hz共享工程或smoke交付，不下载或烧录。操作和构建边界见[PS说明](../docs/ps_stream.md)。
