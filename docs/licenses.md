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

## 当前500Hz应用和FSBL的实际链接

构建ID为ab3e1b7e7a4247c3，匹配清单在tmp/c26/tmp/b/sw/ws/build_manifest.json；这是本轮从正式源码副本完整重建的候选，不是已验发布版。应用和FSBL各自有独立链接图，库SHA、编译输入候选头、提取成员和最终保留符号在tmp/system_finish_20261024/binary_licenses_final/summary.json。编译器及两份ELF的.comment均指向GCC13.4.0，安装头_newlib_version.h声明Newlib4.4.0。

| 实际库 | 应用提取成员数 | FSBL提取成员数 | 声明与对应边界 |
| --- | ---: | ---: | --- |
| libxilstandalone.a | 22 | 17 | 逐成员回查BSP编译源码，含MIT、Cygnus声明及生成配置 |
| libxiltimer.a | 2 | 2 | 逐成员回查实际计时器BSP来源；两套BSP库分别记录SHA |
| libxil.a | 6 | 9 | UART/平台/设备配置实际提取成员；不拿应用库SHA代替FSBL库 |
| libgcc.a | 9 | 5 | 保留GCC13.4.0的GPLv3及Runtime Library Exception原文，实际库SHA另存 |
| libc.a | 62 | 25 | 保留对应Newlib4.4.0发行版汇集声明；各文件条款不同 |
| libm.a | 3 | 未加载 | 应用数学函数库，与Newlib实际库版本一并记录 |
| libg.a | 0 | 0 | 链接图出现LOAD，但没有独立提取成员；文件SHA与libc相同，不算另一份独立实现 |
| libxilffs.a、libxilrsa.a | 未加载 | 0、0 | 当前FSBL链接输入出现，未提取成员；不能凭目录或编译清单说FatFs/RSA进入最终ELF |

FSBL最终符号中保留7个md5/MD5符号，Eric Young相关声明属于本候选实际组成，应随二进制材料保留；现有[原声明](licenses/baremetal_notices.txt)保留完整文字。未发现f_open/f_read/f_close/f_mount保留符号，与本次FatFs库无提取成员相符，不能泛化为所有启动配置都不含FatFs。

项目自有代码仍按根LICENSE处理；原WFDB等声明保留。实际被提取的BSP成员中仍有xuartps_g.c、xcortexa9_g.c、xdevcfg_g.c、xqspips_g.c等生成配置没有单独许可头，记录其实际编译路径/SHA和生成模板来源待核，不能自动补MIT标签。完整源码扫描1495份文本、214份列出编译源、compiled_gpl为空，不等于最终二进制不存在其他许可组成。

## 上游原文与最终分发边界

- [GCC GPLv3原文](licenses/gcc_gpl3.txt)和[Runtime Library Exception原文](licenses/gcc_runtime_exception.txt)取自GCC官方镜像的13.4.0发行分支，不修改字节。例外只按适用文件及条件使用，不能据此给全部工具/IP重新授权。官方说明：[GNU Runtime Library Exception](https://www.gnu.org/licenses/gcc-exception-3.1.en.html)。
- [Newlib4.4.0汇集声明](licenses/newlib_4_4_notices.txt)取自[官方4.4.0.20231231发行归档](https://sourceware.org/pub/newlib/newlib-4.4.0.20231231.tar.gz)中的COPYING.NEWLIB。不是把最新版本许可猜测成供应商版本，也不把汇集文件中所有条款都说成被当前ELF使用。
- 原始URL、发行包/文本SHA与本地原文SHA见[runtime_sources.json](licenses/runtime_sources.json)。源码发行包只留tmp供核对，不把工具安装或全部运行库复制进仓库。
- 当前保留的是匹配版本的上游声明与实际库身份，尚不能证明AMD供应商库相对上游没有补丁；逐选中成员的供应商源码/补丁对应关系继续列为待核项。
- 硬件bit使用AMD IP，不能因bit可生成或项目自有源码为MIT，就认为可以把全部生成IP源码统一按MIT发布。IP及适用EULA独立核对，参照[AMD配置IP说明](https://docs.amd.com/r/2023.1-English/ug892-vivado-design-flows-overview/Configuring-IP)。

以上完成当前候选的实际组成与声明整理，未声明最终分发法律全审通过，未公开上传、提交或替换latest。复核入口见[系统构建与检查](download_guide.md)。


当前2026-10-25 QSPI交付已加入上述匹配FSBL二进制，声明与实际组成仍以本页及runtime500_components_20261025.json为准。已完成本地固化，不表示最终分发许可全审或远端公开发布；详见[当前实现与缺项](../report/report.md)。
