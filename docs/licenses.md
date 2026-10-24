# 裸机交付许可检查

本页核对当前已验ARM运行时构建的BSP/FSBL源码，不修改原third_party.md或旧latest。自动清单是证据入口，不是最终二进制链接或发布许可全审。

## 已核对的组成

| 组成 | 当前源码声明 | 处理 |
| --- | --- | --- |
| standalone、UARTPS及多数AMD驱动、MIT版ps7_init.c | 实际文件头SPDX MIT并保留Xilinx/AMD版权 | [汇集声明](licenses/baremetal_notices.txt)保留已列编译输入中的MIT版权和许可 |
| FSBL md5.c | Eric Young原声明，含二进制材料/署名等条件 | 原许可头完整保留在汇集声明；不可统一改标MIT，最终分发须对应实际链接和署名 |
| FatFs R0.16 ff.c | ChaN 2025原许可 | 保留原声明；其他胶合/生成文件逐项确认，不能因同目录便全部改标MIT |
| standalone print.c/putnum.c | Cygnus Support原许可声明 | 原文保留，不丢失其版权/许可条件 |
| 设备树dt-bindings、ps7_init_gpl.* | 部分GPL/双许可；不是同名MIT版ps7_init.* | 在本次compile_commands列出的输入中未发现GPL声明文件；这只是编译清单核对，不证明所有最终库/头文件和二进制均无GPL组成 |
| 自动生成的*_g.c、配置头、胶合源码 | 有些没有独立许可头 | 保留生成工具/模板来源；不凭空附MIT标签，列为最终分发复核项 |
| ARM GNU工具链运行库、Newlib/libm/libgcc及硬件IP | 不能仅凭BSP头部推断 | 需要链接图、实际库版本及各自许可/例外核对；当前不做完整开源合规完成声明 |

原始全目录扫描1492文件，其中213份列在编译命令中；很多是同一来源的复制/导出，不当作1492个独立组件。扫描中compiled_gpl为空，但compiled_unresolved仍有32份，包含项目自有C、生成配置及上表其他许可；未知不等于违规，也不等于已通过。详细输入及SHA在tmp/system_next_20261024_01/licenses_02/inventory.json。

## 复核命令

```powershell
python -B sim/check_licenses.py --workspace '<项目tmp中的Vitis工作区>' --output tmp/licenses_new
```

只扫描已有工作区并记录许可头/版权/编译输入。新完整构建已增加链接图输出，可进一步区分实际链接对象与仅生成的源码。最终发布时，把与实际交付匹配的许可材料带入交付清单；本轮不替换latest，不公开上传手册、数据库、工具安装或完整BSP缓存。

本轮新硬件对应的工作区`tmp/rbsw01/vitis_workspace`已再次扫描，1492份文本/213份编译源及32份未分类输入的数量相同，清单在`tmp/system_next_20261024_01/licenses_fresh`。实际应用链接图已列出启动对象、项目C对象、libxilstandalone/libxiltimer/libxil及libgcc/libc/libm/libg；LOAD表示链接器读取该输入，不代表其中所有对象都进入ELF。链接图保留在构建清单中，仍须核对工具链各库的许可和例外，不能据此直接宣布可再分发。FSBL采用独立构建/链接，不能拿应用链接图代替FSBL组成审查。
