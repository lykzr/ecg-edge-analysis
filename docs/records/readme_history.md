# README中迁出的历史说明与记录

以下是整理前正文，供报告追溯，不代表新实验；后续README只写工程说明。

## 原位置：build/README.md

# 可复现硬件构建入口

本目录只保存正式Tcl脚本，工具工程、缓存和报告写入tmp/。

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/create_rtl_project.tcl -tclargs xc7z020clg400-2
```

默认创建tmp/vivado/ecg_edge，已有目录即停止。可在器件参数之后另给一个新的输出目录，用于独立验证，不覆盖活动工程。此入口只创建并验证BD及生成输出，不自动综合、实现或生成bitstream。

已有工程可执行build/build_navigator_ecg_system.tcl更新；迁移前生成的工程可能引用旧src路径，应从新入口重新生成，不能将旧缓存作为从零复现证明。完整综合/实现/导出的一键流水线、资源性能汇总与干净环境复现仍列在计划中。

初级组PYNQ为推荐，非本工程当前依赖。实际板卡领航者V2，具体修订仍待实物核对；不可把当前配置当其他板卡预设。


## 原位置：data/README.md

# ECG数据与当前离线入口

当前仅保留v4及其实际依赖。旧v1/v2/v3实现、单记录/旧轮次入口、协议、对应测试和结果已归档到[tmp/history/qrs_20261016/](../../tmp/history/qrs_20261016/README.md)，原字节和SHA256清单保留，不删除。该目录被本地tmp忽略，不是远端共享文件。

## 当前文件

| 文件 | 用途 |
| --- | --- |
| download_mitdb_records.py | 根据当前协议获取并校验原始记录 |
| ecg_dataset.py | 共用212解码、标注读取、幅值转换调用、匹配与统计 |
| benchmark_qrs_v4.py | v4及XQRS/GQRS对照；不再依赖历史候选版本 |
| qrs_v4_protocol.json | 当前配置、原始数据角色与布局迁移后的依赖清单 |
| plot_qrs_benchmark.py | 读取保存的CSV出图，不调算法 |
| results/ | 当前v4两份原始摘要及来源说明 |

src/reference/gqrs_stream.py是v4实际使用的公共流式核心，从旧v3原样拆出；它不是额外维护的历史算法入口。旧RTL逐周期模型ecg_reference.py和输入/滤波参考继续保留。

## 运行

在项目根目录创建隔离环境，输出目录必须不存在：

```powershell
python -m venv tmp/qrs_env
& './tmp/qrs_env/Scripts/python.exe' -m pip install -r data/requirements_qrs.txt
& './tmp/qrs_env/Scripts/python.exe' -B -m unittest discover -s sim -p 'test_*.py'
& './tmp/qrs_env/Scripts/python.exe' -B data/download_mitdb_records.py --output-dir tmp/qrs_current/raw
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --stage development --output-dir tmp/qrs_current/development
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --stage evaluation --output-dir tmp/qrs_current/evaluation
```

当前默认方法为v4/xqrs/gqrs，可用--models v4单独运行。已验证环境Python3.14、WFDB4.3.1、NumPy2.4.4、SciPy1.18.1、matplotlib3.10.9；requirements_qrs.txt固定WFDB而未锁全部传递依赖，实际环境写入summary。

数据来源为[MIT-BIH 1.0.0](https://physionet.org/content/mitdb/1.0.0/)，原始文件保留tmp；全部文件核对官方SHA256，双通道212首值/长度/校验和均核对，按MLII名称选导联。固定360Hz、4096单位/mV与int16饱和，有序一对一±54点匹配，不根据标签拟合时移。

## 结果与版本边界

当前范围19条开发+23条原冻结后新记录，不是CNN划分或48条全库结果。旧独立评估的源码、协议与结果不改写，参见[当前报告](offline_qrs_evaluation.md)与[结果来源](../../data/results/README.md)。本次只拆公共依赖/移动文件；当前协议新增layout_migration并重建依赖清单。现在重跑这些已查看记录属于复现，不能冒充新独立测试。

本轮23项活动软件检查覆盖当前依赖与v4，旧版本专属11项移入归档，旧34项通过记录保留。smoke仍未上板，未训练CNN，未改变RTL/PS/Flash或发布镜像。


## 原位置：data/results/README.md

# 当前v4离线结果

| 文件 | 来源 |
| --- | --- |
| qrs_v4_development_20261016.json | 19条开发记录；来自tmp/history/qrs_20261023/qrs_v4_20261016_01/development_03/summary.json |
| qrs_v4_evaluation_20261016.json | 原冻结后23条记录×v3/v4/XQRS/GQRS，92行；来自tmp/history/qrs_20261023/qrs_v4_20261016_01/evaluation/summary.json |

两份摘要保持原字节，包含当时的历史对照和源码路径/哈希，不因文件整理重新生成结果。evaluation中v4汇总门槛通过、逐记录20/23通过，117定位和205/210的V召回仍失败；不代表CNN或板上验收。smoke仍为NOT_TESTED。

与旧摘要匹配的源码、原协议和清单已归档到[历史目录](../../tmp/history/qrs_20261016/README.md)，摘要中的原相对路径以该归档根解析。完整CSV和原始数据仍在原tmp实验目录，没有移动或删除。v1/v2/v3及100号历史摘要也已移至归档的data/results/。

正式data/qrs_v4_protocol.json是整理后的当前运行清单，包含layout_migration，不冒充原冻结协议；本次文件整理未重新调参或进行新独立评估。说明见[报告](offline_qrs_evaluation.md)。


## 原位置：README.md

# ECG Edge

基于 Zynq-7020 的单导联心电边缘分析原型，用于研究 ECG 数据的软硬件协同处理、QRS 检测与 RR 间期计算。

项目以公开心电数据回放为起点，在软件侧建立参考算法，在 FPGA 侧实现采样处理和事件接口，通过 PS 读取与管理检测结果。目标平台为**正点原子领航者 V2**，器件为 `xc7z020clg400-2`。

项目正在开发中：候选峰算法目前为软件原型，尚未移植到 RTL；**ECG smoke 尚未上板测试**。本项目用于教学与工程验证，不作为临床诊断设备。

## 项目组成

- **软件参考**：ECG 数据读取、整数幅值转换、启动校准、QRS 候选峰检测与标注评估；另保留与现有 RTL 对应的逐周期模型。
- **PL 处理接口**：基础 QRS 候选检测、AXI-Lite 寄存器和事件 FIFO，提供检测位置、RR、队列及溢出状态。
- **PS 自检应用**：发送受控样本，检查配置、事件读出与 FIFO 行为。
- **开发工具**：工程生成脚本、软件/RTL 对照、接口仿真及数据评估工具。

当前数据输入来自公开记录或 PS 生成的合成样本。真实 AFE/ADC 采集尚未接入。

## 目录

| 目录 | 内容 |
| --- | --- |
| `src/rtl/` | FPGA 检测器及 AXI-Lite 接口 |
| `src/ps/` | PS 端应用 |
| `src/reference/` | 软件参考模型与输入处理 |
| `sim/` | testbench、自检和软件/RTL 对照 |
| `build/` | Vivado 配置与工程生成脚本 |
| `board/` | PS 构建、下载与串口操作说明 |
| `data/` | 数据获取、评估脚本与参考结果 |
| `skill/` | 可复用的开发与排错流程 |
| `report/` | 项目计划与报告材料 |
| `docs/` | 寄存器定义与资料索引 |
| `releases/latest/` | 当前发布包及配套说明 |
| `tmp/` | 本地构建工作区、日志和缓存，不纳入交付 |

## 快速开始

所有命令均从项目根目录执行。

### 运行软件参考算法

当前入口为v4，需隔离Python环境及WFDB，完整安装/下载步骤见[数据使用说明](../../data/README.md)。已有环境和原始数据时：

```powershell
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --output-dir tmp/qrs_current/development --models v4
```

输出目录必须不存在。历史算法与实验入口归档于tmp/history/qrs_20261016，正式目录保留当前实现与必要公共依赖。

### 创建硬件工程

使用 Vivado 2026.1，在命令中替换工具安装路径：

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/create_rtl_project.tcl -tclargs xc7z020clg400-2
```

默认在 `tmp/vivado/ecg_edge` 创建工程，已有目录时停止。此步骤创建 PS7/AXI Block Design 并生成工程输出；后续综合、实现、导出与 PS 程序运行见 [构建入口](../../build/README.md) 和 [下载教程](../download_guide.md)。

## 文档导航

- [项目计划与开发优先级](../../report/project_plan.md)
- [板上运行、smoke 与串口教程](../download_guide.md#20-ps-读取配置与受控样本fifo-自检)
- [寄存器接口](../register_map.md)
- [仿真与软件测试](../../sim/README.md)
- [数据、评估方法与结果](../../data/README.md)
- [当前发布包说明](../../releases/latest/README.md)
- [可复用流程](../../skill/README.md)

## 许可证

项目自有代码与文档采用 [MIT License](../../LICENSE)。第三方数据、工具生成内容及参考资料按各自许可使用，详见 [第三方来源说明](../../third_party.md)。


## 原位置：releases/latest/README.md

# 当前发布：Hello World / QSPI

版本：`20261013-hello-world-qspi-v1`。工具：Vivado/Vitis/Bootgen 2026.1。适用板卡：正点原子领航者 V2，Zynq-7020；具体核心板和底板修订尚未独立核实。本镜像运行 Hello World，不执行 ECG 送样或检测。

硬件与软件构建、镜像头检查通过。用户已提供 Flash 校验成功和 PS 复位后 COM14/115200 应用输出；完整断电再上电过程尚未单独确认。证据摘要见 [validation.md](hello_world_validation.md)，文件来源、大小、SHA256 见 [artifacts.json](../../releases/latest/artifacts.json)。

## 烧录

先确认是否替换原有 QSPI 引导内容，写入 offset 0 会覆盖它。断电设置领航者 BOOT_CFG 1=ON、2=ON（JTAG），连接下载器后上电。在 Vitis → Program Flash 中选择：

| 字段 | 内容 |
| --- | --- |
| Image File | 本目录 `BOOT.BIN` |
| Offset | `0x0` |
| Flash Type | `qspi-x4-single`（2026.1 界面名称） |
| Init File | 本目录 `fsbl.elf` |
| Verify after flash | 勾选 |

如果图形界面无法在安装目录创建临时文件，可在 PowerShell 切换到本目录后调用工具；替换安装路径占位符：

```powershell
& '<Vitis安装目录>/bin/program_flash.bat' -f './BOOT.BIN' -fsbl './fsbl.elf' -offset 0x0 -flash_type qspi-x4-single -verify -url TCP:127.0.0.1:3121
```

编程与校验成功后，断电切换 BOOT_CFG 为 1=ON、2=OFF（QSPI），打开 115200 串口再上电，不点击 Run。已处于 QSPI 模式时，重看一次打印可按 PS 复位键。预期输出：

```text
Hello World
Successfully ran Hello World application
```

## 文件与复现

`BOOT.BIN` 是可直接烧录镜像，`fsbl.elf` 是烧录初始化文件；保留匹配 bit/XSA/应用 ELF 便于诊断和重建软件平台。`boot.bif` 引用均在本目录内，运行 Bootgen 前切到本目录。重新打包时输出到新的文件名，核对后再按归档规则更新 latest，不能把重新打包当已实测。

源码与构建配置在项目正式目录，哈希记录在清单；原始构建及完整日志保留在 `tmp/qspi_boot_20261013_01/`。镜像不依赖该 tmp 路径进行烧录。新版本替换 latest 前先将旧 latest 可恢复地归档到 `releases/history/<版本>/`；历史仅保存在本地并被忽略，不删除。


## 原位置：releases/README.md

# 发布产物归档约定

本目录仅将当前发布文件放在 `latest/` 并允许纳入版本管理；历史版本保留在本地忽略目录，不删除。构建工程仍在 `tmp/`。当前 [Hello World / QSPI 发布](../../releases/latest/README.md)已取得用户提供的烧录校验成功及复位后串口输出，完整断电再上电尚未单独确认；按实际验证范围交付。

## 目录与内容

目录使用以下结构，版本标识写入 latest 的说明与清单；每个发布版本至少保留：

```text
releases/
  README.md
  latest/                    当前发布，指定交付文件放行
  history/<版本>/            历史副本，本地忽略、不删除
```

- `README.md`：用途、板卡/修订版本、工具版本、构建来源、程序行为、实际验证阶段、烧录步骤和限制。
- `artifacts.json`：每个交付文件的相对路径、字节数、SHA256，以及源码/构建来源和验收记录位置。
- 实际交付镜像，例如 `BOOT.BIN`。
- 烧录所需的匹配初始化文件，例如 QSPI 的 `fsbl.elf`；其他启动方式按需要确定。
- 必要的板上验收记录，例如 Flash 校验结果、启动拨码、断电上电后的串口输出。实测未覆盖的内容明确列出。

根据交付需要额外保留匹配的 `.bit`、`.xsa` 和应用 `.elf`。如保存 BIF，使用归档目录内有效的相对路径并核查引用；不要原样复制仍指向旧工作区的 BIF 或启动配置。

完整 Vivado/Vitis 工作区、`.runs`、`.gen`、缓存、波形、逐行日志和重复备份继续放 `tmp/`；发布目录保留必要证据摘要。正式源码和可复现脚本在 `src/rtl/`、`build/` 等目录，发布文件不能替代源码。

## 归档时机与检查

1. 明确验收目标：JTAG 运行、QSPI 复位启动、完整断电启动及 ECG 功能是不同阶段，交付说明逐项标明。
2. 用户确认交付当前版本后，使用对应产物及实际证据归档；完整掉电自启动需另外断电上电、不点击 Run 观察，未做则不能标为通过。
3. 首次建立 latest；后续更新前，将旧 latest 可恢复归档到 `history/<旧版本>/`，检查源/目标范围和冲突，再创建新 latest。不移动活动工程，不覆盖历史版本。
4. 对照原产物核对 SHA256，并检查路径、说明和验收证据。
5. 保留原工作区；后续清理另行授权，不因归档自动删除 `tmp/`。

历史版本不覆盖。latest 随当前交付更新，旧文件先归档，不删除；其他旧版本目录同样本地忽略。无法确认板卡修订、源码或某项实测时如实记录，不能把不同机器、不同镜像的验证合并成一次成功。

## 本地保存与团队共享

`releases/` 是本地项目目录，不会被 Windows 自动清理；仍需正常备份。`.gitignore` 默认忽略发布目录中的其他路径，只放行本说明及 latest 的明确文件清单，包含 BOOT.BIN、FSBL、bit/XSA/应用 ELF；即使文件被放行，也不代表已经暂存、提交或推送。

旧文件如果已经被 Git 跟踪，增加忽略规则不会取消跟踪；需按会话授权另行操作索引，不删除本地文件。此次仅改忽略配置和归档文件，Git 仍暂停。远端发布、上传、提交和推送需要另外授权。

## 当前大小参考

2026-10-13 本机文件长度统计（MiB=1048576 字节，不是磁盘占用块大小）：

| 内容 | 大小 |
| --- | ---: |
| `src/rtl/`、`build/`、`sim/` 合计 | 约 34 KiB |
| 本次 Vivado 构建工程 | 45.73 MiB |
| 本次 Vitis 工作区 | 46.30 MiB |
| 本次 QSPI 构建目录合计（含上述两项） | 102.28 MiB |
| `BOOT.BIN` | 3.98 MiB |
| `BOOT.BIN` 与匹配 FSBL 合计 | 4.32 MiB |

该例说明完整工作区大于实际烧录包。后续外设、IP、调试核、数据集和多个历史版本会增加体积；当前数值是快照，不是大小上限。


## 原位置：sim/README.md

# 仿真与软件验证

从项目根目录运行，输出必须选择新目录，完整日志写tmp/：

```powershell
python -B sim/test_mitdb_100.py
& './tmp/qrs_env/Scripts/python.exe' -B -m unittest discover -s sim -p 'test_*.py'
python -B sim/check_ecg_reference.py --vivado-bin '<Vivado安装目录>/bin' --output-dir tmp/reference_check_new
./sim/run_ecg_smoke_test.ps1 -VivadoBin '<Vivado安装目录>/bin' -OutputDir tmp/smoke_check_new
./sim/run_rtl_tests.ps1 -VivadoBin '<Vivado安装目录>/bin' -OutputDir tmp/axi_check_new
```

## 2026-10-15目录迁移后复核

- Python 3.14：数据/幅值/匹配5项与候选峰边界4项通过。
- Vivado XSim 2026.1：六组20915周期、每周期15字段一致，精选报告results/reference_layout.json。
- 同版本smoke合成样本/FIFO仿真通过：PASS ECG_SMOKE real samples。
- AXI分离通道、反压、FIFO与非法地址自检通过：PASS AXI split channels。
- 本机完整结果：tmp/layout_check_20261015_02/reference、smoke、axi；对应根tmp/layout_reference_20261015_02.log、layout_smoke_20261015_02.log、layout_axi_20261015_02.log。

第一次受限环境中xelab不能编译生成C代码；获得工具执行权限后在新目录重跑通过，首次失败日志仍保留在tmp/layout_check_20261015_01。工具权限问题不能当作功能结果；本次没有修改设计来规避错误。

参考逐周期对照针对src/reference/ecg_reference.py与原RTL；不适用于候选峰ecg_peak_reference.py。所有仿真均不能替代板上验证。**smoke尚未上板测试。**

## 历史测试归档

v1/v2专属测试移至tmp/history/qrs_20261016/sim/；v3运行核心测试迁为test_gqrs_stream.py，继续覆盖当前v4依赖。当前活动软件检查23项，历史34项通过证据保留于原日志，不将测试文件移出误写为新增通过。旧ecg_peak_reference.py的历史说明以归档为准。


## 原位置：skill/README.md

# 可复用工程流程

这些流程来自本项目实际失败与验证，按竞赛3.3.5.2整理，供其他队伍参考；不是声称已在其他板卡、PYNQ或其他团队验证的通用软件包。本项目不使用PYNQ，因此不申报通用PYNQ Skill验证成果。

## 1. 黄金参考逐周期对照

- 适用：已明确复位、有效拍、位宽和流水线语义的同步RTL。
- 经验来源：整数参考必须先算旧状态，再应用更新；空拍不推进采样计数，负数右移与位宽回绕不能用浮点替代。
- 用法：以`src/reference/ecg_reference.py`和`sim/tb_ecg_reference.sv`为模板，列出需比较的状态字段，用`sim/check_ecg_reference.py`生成同输入并调用XSim。换题目时替换状态、参考实现和testbench，保留失败时的案例/周期/字段定位。
- 命令：`python -B sim/check_ecg_reference.py --vivado-bin '<Vivado安装目录>/bin' --output-dir tmp/reference_check_new`。
- 已验证效果：当前检测器六组20915周期、每周期15字段一致；候选峰新原型不属于这项一致性结论。
- 失效条件：算法本身可能错但两侧一致；未覆盖参数不能外推；它不替代AXI、板上或真实数据准确率验证。

## 2. 图形界面烧录的临时文件失败定位

- 适用：工具提示无法在安装目录创建临时文件，而从可写目录启动命令行可以成功。
- 经验来源：本机Vitis GUI启动工作目录在安装bin，Flash后端继承cwd，导致创建xicom临时文件失败。
- 用法：先记录报错绝对路径，核对启动入口工作目录和后端是否指定cwd；确认相对启动器依赖，再使用绝对入口与可写工作目录。完整定位过程见`board/download_guide.md`第19节。
- 已验证效果：本机快捷方式读回正确；用户从可写目录命令行烧录Verify成功。GUI修改后重新烧录尚未实测，不能宣称GUI实测通过。
- 失效条件：硬件未上电、JTAG不通、Flash型号/镜像错误不能靠改cwd解决；不要把增加管理员权限或修改安装目录ACL当默认方案。

## 3. 串口自检证据分级

- 适用：PS通过MMIO验证PL寄存器、事件队列等接口。
- 用法：以`src/ps/ecg_smoke/main.c`为例，先核对配置和初态，再送受控输入，分别检查字段、消费、溢出及清提示；输出BEGIN、逐阶段PASS与最终失败计数。
- 已验证效果：当前接口真实样本RTL仿真通过、PS ELF构建通过；**smoke尚未上板测试**，不能将这项当板上成功案例。
- 失效条件：无软件复位时必须先重新配置PL；只看到Hello World、Build成功或仿真PASS都不足以证明PS→PL实测通过。

## 迁移与复用边界

脚本从自己的位置定位项目根；换板必须重新核查器件、DDR、MIO、时钟和地址，不复制本机路径/串口号作为他人默认。技能依据与失败轨迹先保留实验记录，完整提示词/模型回答与自我纠错交付仍是计划中的工作，不以本页代替原始协作记录。


