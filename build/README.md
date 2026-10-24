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



## 独立启动学习候选

build_ecg_auto.tcl接受一个不存在的项目tmp输出目录，复制并冻结ecg_qrs_auto.sv，生成只替换检测器实例的AXI包装，沿用领航者板级配置并综合/实现/导出匹配bit/XSA/ps7_init。原检测器、正式共享工程和smoke不覆盖。PS工作区由board/build_ecg_auto.py通过Vitis Python生成；环境变量和预热/身份约定见[候选说明](../docs/qrs_auto.md)。待验产物留tmp，不能直接替换已验latest。

## 当前360Hz完整重建

`python -B board/rebuild_system.py --output tmp/rebuild_new --vivado-bin "<Vivado>/bin" --vitis-bin "<Vitis>/bin"`从新目录执行BD、综合、实现、bit/XSA及匹配ARM ELF构建。脚本显式核对正式BD的全部PS7及ECG参数；不改变PS配置、不下载。输出必须是新的项目tmp英文目录，产物、日志、链接图和清单均保留。`--hardware-from`只用于显式接续同轮已生成硬件，摘要会标明来源，不能冒称该次从零构建。

Windows建议使用靠近项目根的短输出路径，例如`tmp/rb01`，避免在多层实验目录下再创建Vitis工作区。若Vitis返回`Invalid project location`，保留失败目录和日志，在另一个短路径重试；不要修改安装目录权限。脚本要求实际ELF及链接图存在才写成功清单；Vitis启动器退出码本身不能证明构建成功。当前重建只覆盖原硬件配置与360Hz ARM运行时，不包含最终CNN或新QRS的PL实现。

## 500Hz ARM构建

同一board/build_runtime.py通过ECG_RUNTIME_RATE=500生成独立ecg_runtime500组件；窗口/FIR系数已保存，build/generate_rate500_runtime.py核对冻结360Hz父本SHA后生成独立源到新tmp。系数复核分别使用generate_rate500.py与generate_window500.py，实际步骤见[500Hz说明](../docs/rate500.md)。
