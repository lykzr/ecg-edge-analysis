# Zynq-7000：Vivado、Vitis、JTAG 下载与串口通用教程

本文说明从硬件工程到裸机程序运行的完整流程。菜单以 **Vivado / Vitis Unified IDE 2026.1** 为基准，处理器以 Zynq-7000 的 Cortex-A9 为例；其他版本可能调整菜单。板卡的电源、启动跳线、DDR、时钟、MIO 和串口接线必须查对应板卡手册，不能直接套用另一块板的预设。

第一次验证的目标是：电脑识别目标芯片，下载匹配的硬件设计，初始化 PS，运行一个串口输出程序。Hello World 仅验证这条基础链路；后续算法、外设或 AXI 接口需要单独测试。

## 1. 先分清文件与操作

| 项目 | 用途 | 不能据此认定的结果 |
| --- | --- | --- |
| Vivado 工程、RTL、BD、XDC | 描述硬件、器件、接口和约束 | 工程能打开不等于匹配实物 |
| `.bit` | 配置 PL 的逻辑电路 | 单独下载不会运行 PS 的 C 程序 |
| `.xsa` | 给 Vitis 的硬件交接文件；可包含 bitstream | 不能替代应用 ELF |
| Vitis Platform / BSP / domain | 按 XSA 生成处理器、驱动和系统支持 | 平台 Build 成功不等于应用已运行 |
| `.elf` | 编译并链接后的 PS 应用 | 应用 Build 成功不等于已下载 |
| `ps7_init.tcl` / FSBL | 初始化 PS 时钟、DDR、MIO 等 | 必须与硬件设计匹配 |
| `BOOT.BIN` | 按启动方式打包的引导镜像 | 创建镜像与写 Flash 是两步操作 |

**Build** 是生成文件，**Run** 是下载并运行应用，**Debug** 是带断点运行。JTAG 测试通常把配置和程序送到易失性资源；断电后需要重新下载。需要脱离电脑上电启动时，才另做启动镜像及 QSPI/SD 流程。

JTAG 负责调试下载，UART 负责串口输入输出。连接 USB 串口并看到文字，不代表 ELF 是通过 UART 下载的；Vitis 左侧 Run 可以同时使用 JTAG 启动应用、UART 显示结果。

## 2. 建立清楚的目录结构

先准备一个英文路径的项目根目录，以下是示例，不要求创建指定盘符：

```text
<project>/
  src/rtl/                  正式硬件源码
  build/                可复现硬件构建脚本
  src/ps/               自己维护的应用源码
  docs/                 教程和说明
  tmp/
    vivado_build/       派生硬件工程及输出
    vitis_bringup/      独立的 Vitis 工作区
      ecg_platform/    软件平台组件（示例名称）
      hello_world/     应用组件（示例名称）
      _ide/            此工作区的 IDE 配置
```

打开 Vitis 时，将 **Workspace** 设为 `<project>/tmp/vitis_bringup`。创建平台或应用的 **Name and Location** 页面还要再次检查 Location，确认最终目录在这个工作区内。工作区用于组织组件，Location 决定组件实际落盘位置；不能只看组件名称。

`tmp` 在本项目表示可重建的派生工作区，里面生成 bit/XSA/ELF 是正常的。正式源码和可复现配置仍应保留在正式目录中；不要把自己编写的唯一一份代码留在以后可能清理的构建目录。对重要测试版本记录源码版本、工具版本和产物哈希。

若先把仓库根目录当成 Vitis 工作区，又按默认位置创建组件，就会在仓库根目录出现平台和应用两个文件夹。这是创建位置造成的正常工具行为。

### 已建错位置时如何处理

先保存、关闭 Vitis，保留原组件及应用源码。优先用该版本支持的导出/导入，或在新工作区按同一份 XSA 重建平台并导入原应用源码。生成目录可能含绝对路径，**仅剪切文件夹、只改 XSA 路径或只改 launch.json，不能保证迁移完整**。迁移后重新 Build，并核对运行配置中的 bit、初始化文件和 ELF。

本次两个组件是默认示例，经归档后在 `tmp/vitis_bringup` 重建；原文件保存在 `tmp/backup/vitis_root_components_20261013_01`。根目录原有其他 IDE 元数据未清理。下次打开 Vitis 要选新的工作区，避免继续使用旧工作区登记。

## 3. Vivado：生成 bitstream 和 XSA

1. 打开与实物匹配的工程，检查器件、PS 配置、DDR、时钟、MIO、地址和约束。不能把“综合通过”当作板卡匹配证明。
2. 检查 BD，生成需要的输出产品和顶层 wrapper；确认 wrapper 是顶层。
3. 在左侧 **Flow Navigator** 中依次执行 Run Synthesis、Run Implementation、Generate Bitstream。根据弹窗可自动继续后续步骤。
4. 查看最终时序和 DRC；失败或过期的运行不能拿旧 bitstream 冒充新结果。
5. 选择 **File → Export → Export Hardware**，导出固定硬件设计，勾选 **Include bitstream**。保存到明确的构建输出目录。
6. 记录本次 `.bit` 和 `.xsa` 的位置、修改时间和来源。Vitis 平台使用这份 XSA，运行配置也使用对应 bitstream。

Vivado 的 Flow Navigator 位于窗口左侧，包含 Synthesis、Implementation、Program and Debug 等分组；Vitis 左侧通常叫 **FLOW**，其中 Component 下拉框选择平台或应用。两处功能不同。

若正在看的 Vivado 工程提示 Out-of-date，而 bit/XSA 来自另一个独立构建工程，应核对产物的构建记录，不能仅根据当前窗口判断产物是否更新。

## 4. 供电、JTAG 与器件识别

按板卡手册连接电源并打开开关，再连接 JTAG。下载器 USB 被电脑识别，不能证明目标板获得了工作电源；是否支持从某个 USB 口供电，要查板卡电路。RTC 纽扣电池通常只维持时钟，不给整个 Zynq 系统供电。用户按键通常也是程序输入，不能代替电源开关。

Vivado 中打开 **Open Hardware Manager → Open Target → Auto Connect**。观察 Hardware 树：

| 显示 | 含义 |
| --- | --- |
| localhost Connected | 与本机硬件服务器连通 |
| Digilent 等 target 为 Open | 下载器目标已打开 |
| Number of devices = 0 | 没有发现链上芯片，尚不能下载 |
| 出现 `arm_dap_0` 和 `xc7z020_1` 等 | 已识别 Zynq 的调试接口和 FPGA 器件 |
| FPGA 为 Not Programmed | 芯片已识别，尚未配置 PL |
| There are no debug cores | 当前未发现 ILA 等调试核；普通设计可以没有调试核 |

如需先单独验证 PL 下载：右击 FPGA 器件 → **Program Device** → 选择本次 `.bit` → Program。没有 ILA 的设计通常不需要 `.ltx` probes 文件。确认下载完成及器件配置状态。

如果之后 Vitis 的 Run 配置启用了 Program Device，Vitis 会在运行流程中再次配置 PL；每次测试不必重复手动在 Vivado 下载。更改接线前断电；器件数量为 0 时先查电源和 JTAG 接线，再查目标连接和下载频率。

## 5. Vitis：创建平台

1. 启动 Vitis Unified IDE，选独立工作区，例如 `<project>/tmp/vitis_bringup`。
2. **File → New Component → Platform**，填写平台名称和 Location。
3. Flow 页面选择 Hardware Design，点 **Browse** 选择自己导出的 `.xsa`。下拉列表中的 zc702、zc706 等是工具自带设计，不能仅因同为 Zynq 就替代自己的 XSA。
4. OS and Processor 页面，裸机选择 **standalone**，Zynq-7000 单核入门应用通常选择 **ps7_cortexa9_0**。
5. 如保留 Generate Boot Artifacts，工具可以生成 Zynq FSBL；是否生成 FSBL与实际 Run 是否选择 FSBL 初始化是两个问题。
6. 完成向导。左侧 FLOW 的 Component 下拉框选平台，点击 **Build**。
7. 看到平台构建成功后，再创建应用。

操作依据：[AMD UG1400：从 XSA 创建平台](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Creating-a-Platform-Component-from-XSA)。

## 6. Vitis：创建并 Build Hello World

1. 打开 **View → Examples**，选择 Hello World。
2. 点击 **Create Application Component from Template**。
3. 填写应用名和 Location，选择刚生成的平台以及它的 standalone domain。
4. 完成后，在 FLOW 的 Component 下拉框选择应用，点击 **Build**。
5. 若弹出 Application–Platform Build Dependency，初次调试可选 **Always build platform with application**，再点 **Save in Workspace Preference**，使此设置只针对当前工作区。
6. 查看应用自己的 Build 输出；平台成功不能代替应用成功。确认生成对应 `.elf`。

修改平台 BSP 或更换 XSA 后，需要先更新并构建平台，再重建应用，避免旧支持库与新硬件混用。默认示例可以直接测试；改成自己的程序后，要保护并维护应用源码。

操作依据：[AMD UG1400：从示例创建应用](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Creating-an-Application-Component-from-Examples)。

## 7. 先打开串口，再 Run

1. 将板载 USB-UART 接口接到电脑。JTAG USB 接口和 USB-UART 接口可能分开，按板卡标注区分。
2. Windows 设备管理器中查看“端口（COM 和 LPT）”，记录该板的 COM 号；必要时用插拔前后的变化确定。
3. Vitis 选择 **Vitis → Serial Monitor**。选择这个 COM，波特率与程序一致；常见入门配置为 **115200、8 数据位、无校验、1 停止位、无流控**。
4. 打开串口。看到 `Opened with baud rate: 115200` 只表示串口已打开，尚未证明板上应用运行。
5. 保持终端打开，再启动应用，避免漏掉只打印一次的 Hello World。

同一个 COM 通常只能由一个串口工具占用。若端口打不开，关闭其他终端；若乱码，先核对波特率。若完全无输出，核对程序是否真的运行、BSP 的 stdout UART 与板载接口是否对应。

Hello World 只打印一次。程序已运行但打开串口较晚时，在已经正确设置为 QSPI 启动的领航者上，保持串口打开，按 **PS 复位键**即可重新启动并观察打印，不必为了重看输出反复开关电源。PS 复位键与 PS_KEY1 等用户按键不同；JTAG 临时下载的应用不能据此保证自动重跑，可能需要重新 Run。完整验证断电后的自动启动时，仍单独做一次断电再上电。

操作依据：[AMD UG1400：Serial Monitor](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Serial-Monitor)。

## 8. 检查 Run / Debug 启动配置

选中应用，从 FLOW 的 Run/Debug 设置入口打开 Launch Configuration；首次 Run 时也可能提示创建配置。核对以下内容后运行：

| 项目 | 裸机 Zynq-7000 初次调试的检查点 |
| --- | --- |
| Target Connection | 本地 JTAG 调试连接，能够发现目标芯片 |
| Target Setup | 独立启动目标的模式，而不是仅附加已运行程序 |
| Reset | 需要从已知状态启动时启用系统复位 |
| Program Device / Bitstream | PL 设计参与运行时选择匹配的 bitstream，并允许配置器件 |
| Board Initialization | 选择来自同一硬件设计的 PS 初始化 Tcl 或 FSBL |
| Tcl 初始化 | 使用对应 `ps7_init.tcl`，执行初始化及所需 post-init |
| Processor / ELF | 选择应用使用的 Cortex-A9 核，以及刚构建的应用 ELF |
| Stop at entry | 直接看输出时不停止；调试停在 main 时需 Resume 后才继续打印 |

PS 的时钟、DDR、MIO 等必须先正确初始化。工具支持 **Tcl 初始化** 和 **FSBL 初始化**，选择一种匹配设计的流程即可。平台目录中存在 fsbl.elf，不代表本次一定执行了 FSBL。

点击 **Run** 后观察下载及启动日志，再观察串口。若点 **Debug** 停在入口，按 Continue/Resume 继续。默认 Hello World 示例运行一次后结束，再观察一遍可以重新 Run；上电后按某个板载按键不会自动重新下载应用。

操作依据：[AMD UG1400：启动配置 Main Page](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Main-Page)。

## 9. 如何判断成功

默认示例可能输出：

```text
Hello World
Successfully ran Hello World application
```

以实际源码中的打印内容为准。应用对应的下载/启动日志和 UART 输出共同证明基础运行链路；没有进一步证据时，不能认定自定义 PL 接口、DMA、ADC 或算法已经验证。

若前面出现 U-Boot、Starting kernel、SD 或 PHY 错误，再出现自己的应用打印，可能是原有启动介质的软件先输出，随后 JTAG 启动了自己的程序。先按时间和源码辨认日志来源，不把旧启动系统的错误直接归因于新 Hello World。

使用 JTAG Run 通常不会替换原来的 QSPI 启动镜像。断电后再次启动仍出现原厂输出，与此前 JTAG 测试成功可以同时成立。

## 10. 常见故障排查

| 现象 | 先做什么 |
| --- | --- |
| No devices detected / devices=0 | 查板卡供电、开关、JTAG 接口和方向，然后重新打开 target |
| 只看到下载器 Open | 展开 target 看器件，不能把下载器识别当芯片识别 |
| Program Device 灰色 | 先选已识别的 FPGA 器件；devices=0 时无法配置 |
| 创建平台不知道选什么 | Browse 自己的 XSA；使用板卡匹配的硬件设计 |
| 平台 Build 完但没有输出 | 继续 Build 应用、打开串口、检查 Run 配置并运行 |
| 串口打开但无 Hello World | 查 COM、stdout UART、是否停在 main、PS 初始化及实际下载的 ELF |
| 搬目录后找不到文件 | 从新工作区导入或重建，重新核对平台、CMake、bit、初始化文件及 ELF 路径 |
| 新组件又出现在仓库根目录 | 检查打开的 Workspace 和创建向导的 Location |
| 一断电程序就没了 | JTAG 临时运行符合预期；脱机启动需要另一套镜像制作及启动介质操作 |

## 11. 本项目当前对应位置与验证范围

以下是本项目示例映射，通用步骤不依赖某个用户名或盘符：

- 当前硬件交接：`tmp/pre_download_20261013_01/ecg_system_candidate.xsa`，对应 bitstream 在同目录。
- 整理后的 Vitis 工作区：`tmp/vitis_bringup`，平台 `ecg_platform`，应用 `hello_world`。
- 根目录旧组件归档：`tmp/backup/vitis_root_components_20261013_01`，含文件哈希清单及新工作区重建日志。
- 实物已由用户确认是领航者 V2；所用设计 UART0/MIO14–15、串口 115200。实物核心板和底板具体修订版本仍待核对。
- 用户已提供 Hello World 板上串口输出。迁移后构建及配置检查属于本地验证；迁移后的再次上板运行仍需用户执行。

重新打开 Vitis 时，选择 **本项目根目录下 `tmp/vitis_bringup`**，然后按第 7—8 节打开串口和 Run。下一项 ECG 验证应先读配置寄存器，再送受控样本核对事件 FIFO；Hello World 示例没有完成这些动作。

领航者接线、ECG 验收和资料依据见下列补充章节，ECG 接口见 [register_map.md](../docs/register_map.md)。

## 12. 没有 SD 卡：将程序固化到 QSPI

QSPI 是板上的非易失存储器。自启动路径是 BootROM → FSBL → PL 配置 → 裸机应用。镜像必须与板卡和硬件配置匹配，不能直接把 JTAG 使用的 ELF 当启动镜像写进去。

### 12.1 硬件与软件准备

Vivado 的 PS7 必须启用对应 QSPI 接口。本项目配置依据配套 Vitis 指南第 7 章、官方 `6_axi_gpio_fsbl` 工程与核心板原理图：单片 W25Q256、Single SS 4bit IO、MIO1..6，Bank0 为 3.3V，无反馈时钟、不启用第二片选。当前构建脚本已经加入此配置。没有 SD 卡不要求同时启用 SD 接口。

修改 PS 配置后重新生成 bitstream，导出包含 bitstream 的 XSA，再由新 XSA 构建平台、FSBL 和应用。原先 `tmp/pre_download_20261013_01` 的 XSA 未启用 QSPI，仅保留为旧 JTAG 测试版本。

本次独立产物目录是 `tmp/qspi_boot_20261013_01`；软件工作区在其 `vitis_workspace` 子目录。该目录的 `BOOT.BIN` 是 **Hello World 自启动测试镜像**，不是 ECG 样本回放程序。

### 12.2 通用打包操作

Vitis 菜单 **Vitis → Create Boot Image**，器件选 Zynq，创建新 BIF。分区顺序为：

1. 匹配平台的 `fsbl.elf`，属性 `bootloader`。
2. 匹配的 `.bit`，普通分区。
3. 应用 `.elf`，普通分区。

指定 BIF 和输出 `BOOT.BIN` 的路径，点击 Create Image。也可以使用 Bootgen 从 BIF 打包。本项目本次生成的 `boot.bif` 采用相对路径，从该文件所在目录运行；不要只搬走 BIF 却留下一组失效的相对引用。

依据：[AMD UG1400 2026.1：创建启动镜像](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Creating-a-Boot-Image)。

### 12.3 用户执行写入

写入前确认是否需要保留原有 QSPI 启动系统；写入起始区域会替换原厂引导内容。尚未备份原有 Flash，不能声称已经有恢复镜像。

1. 断电，领航者 BOOT_CFG 设为 **1=ON、2=ON（JTAG）**，按编号和 ON 丝印判断。连接下载器，再上电。
2. 在 Vitis 打开本次 `tmp/qspi_boot_20261013_01/vitis_workspace` 工作区，菜单选 **Vitis → Program Flash**。
3. Connection 选本地 JTAG/hw_server；Image File 选本次 `BOOT.BIN`；Offset 为 `0x0`；Flash Type 为本板单片配置 `qspi_single`。
4. Init File / FSBL 选择该工作区 `ecg_platform/export/ecg_platform/sw/boot/fsbl.elf`；勾选 **Verify after Flash**。
5. 核对所有路径属于本次产物后点击 Program。等待编程及校验成功；失败时保留完整日志，不反复盲目擦写。烧写中保持稳定供电。
6. 关闭电源，BOOT_CFG 改为 **1=ON、2=OFF（QSPI）**。
7. 打开对应 115200 串口，再上电，**不点击 Run**。若自动打印 Hello World，才证明此次 QSPI 自启动成功。

依据：领航者配套指南第 7.5 节启动表及 [AMD UG1400 2026.1：Programming Flash](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Programming-Flash)。新版菜单是 Vitis，旧版教材中的 Xilinx 菜单不能照搬。

本助手生成文件和检查构建，不执行板上拨码、Flash 写入或断电测试；最终自启动结果以用户实际操作和串口记录为准。

## 13. 领航者 V2 接线与工程检查

本节由原上板说明合并而来，接法依据 A 盘主目录指南。核心板、底板具体修订版本仍须核对；主目录与 V3.7 分支不能混用。通用工具步骤见第 3—8 节。

1. 断电后调整拨码、跳帽和接线，记录核心板、底板丝印版本及下载器型号。
2. 使用 Vivado 支持的 JTAG 下载器，USB 端接电脑，下载线接底板 14-Pin JTAG 调试口；按标识核对方向与 1 脚。底板 14 针口与核心板 6 针口连接同一 JTAG 网络，不同时接两个下载器。
3. 单独用 USB 数据线连接底板 `USB_UART` 与电脑。CH340 串口 USB 不能代替 JTAG 下载器；不要混淆 USB HOST/SLAVE 接口。
4. 主目录手册的串口跳帽 `P5` 连接串口芯片 RX 到 `PS_TX`、TX 到 `PS_RX`；按实物丝印与匹配图纸核对。
5. 匹配主目录手册的 `BOOT_CFG`：1=ON、2=ON 为 JTAG；1=ON、2=OFF 为 QSPI；两位 OFF 为 SD。按开关编号与 ON 丝印判断，设置后再上电。
6. 用匹配电源供电并打开开关，分别确认 JTAG 器件和串口 COM 口。缺驱动时先查设备与系统，不自动运行下载盘安装器。串口使用 115200、8 数据位、无校验、1 停止位、无流控，COM 号按本机识别结果选择。

构建时使用 `build/build_navigator_ecg_system.tcl` 生成或核对 BD；顶层为 `ecg_system_wrapper`，器件为 `xc7z020clg400-2`。记录所用源码、构建目录、bitstream 与 XSA，旧日志/XPR 中的历史路径需另行核对。BSP 标准输入输出应对应本设计的 UART0/MIO14–15；PS 初始化文件必须来自同一硬件设计。

10 月 6 日的 `vivado/ecg_edge/ecg_edge.runs/impl_1/ecg_system_wrapper.bit` 早于领航者修复，不能当新版产物。10 月 13 日的 JTAG 候选 bit/XSA 位于 `tmp/pre_download_20261013_01/`，Hello World ELF 位于 `tmp/vitis_bringup/hello_world/build/hello_world.elf`。原上板说明中“只有旧 bit、未找到 XSA/ELF”的描述已经过时。

上述位置对应已记录的 JTAG 候选版本。QSPI 配置及构建由另一项工作继续推进，新产物应另核对来源，不把旧 JTAG 版本与新 FSBL/应用混合使用。

## 14. ECG 接口的下一阶段验收

目前 ECG 部分是 PS7/AXI 硬件框架与 QRS 候选检测 RTL。Hello World 已有用户提供的板上串口输出；ECG 回放应用、采集接口、显示驱动及 ECG 结果输出仍待开发。PL 不会自行从串口或电极获取样本，也没有用于用户 LED 闪烁的顶层接口。

已记录的 JTAG 配置使用 FCLK0 100 MHz、`proc_sys_reset`、默认 360 Hz、16 位有符号样本和深度 8 的事件 FIFO。FPGA 时钟频率不能当作 ECG 采样率；接入数据前须核对实际采样格式和速率。

| 验证阶段 | 应记录的证据 | 结论边界 |
| --- | --- | --- |
| 配置 PL | 工具下载完成及 DONE 状态 | 不证明 PS 应用或 ECG 算法运行 |
| 初始化 PS 并运行 Hello World | 同一 XSA 的初始化流程、ELF、串口输出 | 仅验证基础 ARM/串口链路 |
| 读取 ECG 参数 | `0x43C00024`、`0x43C00028`、`0x43C0002C`，默认期望 360、120、200 | 须与本次构建参数一致 |
| PS 送样并消费事件 | 写 `0x43C00000`；读 FIFO 状态、位置、RR、序号，读完再弹出 | 单一消费者操作，定期记录溢出及丢弃计数 |
| 固定 ECG 数据回放与比对 | 输入数、事件、RR、丢弃数及软件/仿真同输入参考 | 所测样本结果不能代替总体准确率或真实采集验证 |

完整地址、权限及消费顺序见 [寄存器接口](../docs/register_map.md)。访问 PL 前必须初始化 PS、时钟和复位，避免把 AXI 访问异常误判为算法错误。本机历史过程和完整验证证据集中在本地忽略的 lykzr.md；可共享阶段摘要见 [项目计划](../report/project_plan.md) 与 [100号结果说明](../data/README.md)。

自动启动流程沿用第 12 节：固化 Hello World 只会运行示例，不会自动进行 ECG 检测。生成镜像、写介质和断电验收分别记录；本次文档合并未生成镜像或操作 Flash/SD，也未验证 QSPI 自启动。SD 路径另需准备匹配的 FAT32 卡和启动模式。

## 15. 合并内容的资料依据

以下保留原上板说明的来源定位和历史阅读范围；本次只合并文档，没有重新逐页审读指南或复核在线菜单。

- A 盘 `2_文档教程/2_【正点原子】领航者ZYNQ之嵌入式Vitis开发指南V1.2.pdf`：第 2.5 节第 52–58 页（接线、P5、JTAG、串口、Hello World）；第 7.4–7.5 节第 155–159 页（固化原理、启动模式）。原核查已读取相关文字并查看接线与启动表页面。
- A 盘 `2_文档教程/1_【正点原子】领航者ZYNQ之FPGA开发指南V3.4.pdf`：第 5.2.2 节第 115–116 页（BOOT_CFG）、第 5.2.7 节第 119 页（JTAG）。原核查已查看相关原理图页面。
- [AMD UG908：连接硬件目标](https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Opening-Hardware-Target-Connections)、[下载与 DONE](https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Programming-the-Hardware-Device)。
- [AMD UG1400：由 XSA 创建平台](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Creating-a-Platform-Component-from-XSA)、[创建应用](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Creating-an-Application-Component)、[启动配置](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Main-Page)、[Standalone 调试](https://docs.amd.com/r/en-US/ug1400-vitis-embedded/Debugging-Standalone-Application-Component)。

## 16. 2026-10-13：本次 QSPI 镜像已准备

本轮已完成 QSPI 配置修改、独立硬件构建、软件平台/FSBL/Hello World 构建和 Bootgen 打包；前文关于其他文档整理任务“未生成镜像”的记录仍是其当时的操作边界，不代表本轮进度。

- 待写入镜像：`tmp/qspi_boot_20261013_01/BOOT.BIN`，4169224 字节。
- 写 Flash 的 Init File / FSBL：`tmp/qspi_boot_20261013_01/vitis_workspace/ecg_platform/export/ecg_platform/sw/boot/fsbl.elf`。
- 打开 Vitis 使用本次 `tmp/qspi_boot_20261013_01/vitis_workspace` 工作区。
- 构建及镜像头检查通过；最终 WNS +0.329 ns、WHS +0.057 ns，DRC 无违规。产物与哈希见该目录 `artifacts.json`。
- 用户操作交接见该目录 `READY.md`；Program Flash 使用 Offset `0x0`、`qspi_single`、本次 FSBL，并勾选 Verify after Flash。

本轮没有写板上 Flash，没有完成断电自启动实测，也没有备份原有 QSPI 内容。先在 JTAG 模式写入并校验，再断电切到 QSPI 模式；上电不点击 Run，观察 Hello World。此镜像运行默认示例，不执行 ECG 样本回放。

## 17. 2026-10-13：最新板上进度

用户已提供 Flash 校验成功日志；COM14/115200 在复位后显示 Hello World 和 Successfully ran Hello World application。以上为用户操作所得证据，更新第 16 节的候选准备阶段：当前已完成用户侧写入校验及复位后输出观察。完整断电上电验收尚未从本条反馈单独确认，正式发布归档仍按 releases/README.md 的验收要求执行。

## 18. 当前发布入口与历史保留

用户已授权归档当前版本，最新发布入口改为 `releases/latest/`，其中含 BOOT.BIN、匹配 FSBL、bit/XSA/应用 ELF、相对路径 BIF、清单及烧录/验证说明。今后烧录可直接使用该目录的 BOOT.BIN 和 fsbl.elf，不必依赖 tmp 路径。完整操作见 [当前发布说明](../releases/latest/README.md)。

只放行 latest 的明确交付文件；历史版本、本次及其他构建留在本地忽略目录，不删除。版本号及验证范围记录在清单中，后续替换 latest 前先归档旧版本。此次发布范围为用户已提供的烧录校验成功和复位输出，完整断电启动仍未单独确认。

## 19. 图形界面烧录的本机启动目录问题

本机首次 GUI 烧录失败的原因已定位：Vitis 开始菜单快捷方式的起始位置是安装目录 bin，普通用户没有写权限；GUI 的 Program Flash 子进程没有指定 cwd，因此继承了该位置，并在创建 xicom_zynq_bin 临时文件时失败。用户切到可写项目目录执行工具后校验成功。

本机入口为 `tmp/vitis_launcher/Open-Vitis.lnk`，先关闭已打开的 Vitis，再从文件资源管理器双击该入口；它使用绝对路径调用 vitis.bat，设置可写工作目录并打开当前软件工作区。之后仍可用 Vitis → Program Flash，选择 releases/latest 中的 BOOT.BIN 与 fsbl.elf。入口的语法、路径和工作目录检查通过，GUI 再次烧录尚待实际确认。无需为测试入口而重复擦写已成功的镜像。

其他成员应核查自己的快捷方式和工作目录；本机路径只用于本机。原 AMD vitis.vbs 相对调用 vitis.bat，单独改原快捷方式的起始位置可能导致找不到工具，应使用绝对路径的启动入口或对应启动方式。不要为这个问题扩大安装目录写权限。

2026-10-13 后续更新：用户选择直接修正原入口，系统级开始菜单的 Vitis 2026.1 快捷方式已备份并修改为绝对路径 vitis.bat，起始位置与 -w 参数均指向本机可写工作区。关闭旧 Vitis 后，从开始菜单重新启动即可；额外入口仍保留作备用。原安装目录权限未变。快捷方式回读检查成功，GUI 烧录完整重试尚未执行。

## 20. PS 读取配置与受控样本/FIFO 自检

正式应用源码在 `src/ps/ecg_smoke/main.c`，可复现构建脚本 `board/build_ecg_smoke.py`。当前已在独立工作区 `tmp/ecg_smoke/vitis_workspace` 构建平台及 `ecg_smoke` 应用，ELF 在该目录 `ecg_smoke/build/ecg_smoke.elf`。使用 latest 的匹配 XSA 和 bitstream，没有更改 RTL、PS 参数或当前 Hello World 发布镜像。此阶段先做 JTAG 运行，不写 Flash。

### 用户运行

1. 断电，将领航者 BOOT_CFG 设为 **1=ON、2=ON（JTAG）**，连接下载器并上电。
2. Vitis 切换到本项目下 `tmp/ecg_smoke/vitis_workspace` 工作区；欢迎页可使用 Set Workspace。原开始菜单入口仍默认打开先前 QSPI 工作区，本次需要主动切换。
3. 打开 COM14（若端口变化则选实际串口），115200。保持串口打开。
4. 在左侧 FLOW 的 Component 下拉框选择应用 **ecg_smoke**，点击 **Run**。新工作区已构建，不需要创建新的平台或应用。
5. 启动配置需要 Program Device=true、系统复位、匹配的 ps7_init.tcl、Cortex-A9 核 0、ecg_smoke.elf，且不停止入口；生成的本机配置已核对。没有软件复位寄存器，每次自检都要重新配置 PL，不能只对已运行的处理器下载 ELF。
6. 保存从 BEGIN ECG_SMOKE 到最终结果的完整串口日志。应出现下列关键行：

```text
BEGIN ECG_SMOKE base=0x43C00000
CONFIG rate=360 window_ms=120 refractory_ms=200
PASS CONFIG
PASS ZERO_INPUT
EVENT seq=1 index=79 rr=0
EVENT seq=2 index=439 rr=360
EVENT seq=3 index=799 rr=360
EVENT seq=4 index=1159 rr=360
PASS EVENT_FIELDS_AND_POP
PASS FIFO_OVERFLOW queued=8 total=16 dropped=4
PASS FIFO_DRAIN_AND_OVERFLOW_CLEAR
PASS ECG_SMOKE failures=0
```

失败会输出 FAIL 的字段、实际值和预期值。若停在 BEGIN 之后而没有 CONFIG，先保存调试输出并检查 PL 是否配置、PS 初始化/AXI 时钟复位及地址；不要据此直接认定算法有错。若初始计数或阈值不匹配，检查是否真正重新配置了 PL。

### 测试内容与边界

读取配置 360Hz、120ms、200ms，并检查新复位状态；先写 100 个零，再写 4 组交替正负的 ±20000 单样本脉冲，每组随后 359 个零，逐个读队首字段后弹出。默认积分窗口 43 点、位置回移 21 点，因此事件位置为 79、439、799、1159，首次 RR=0，后续 RR=360。脉冲后积分值应为 20000，间隔结束回到 0。

接着送 12 组同样的脉冲而不消费：应保留前 8 个事件，队首位置 1519、序号 5 不变；总计 16 个事件、丢弃 4 个。清溢出提示不得清累计丢弃计数，再按序核对并消费 8 个事件，空队列字段归零。共发送 5860 个样本。

输入是接口测试用合成波形，按 AXI 吞吐快速发送，不按墙钟每秒 360 次节拍发送。RR=360 是样本数，不能据此次测试声称实测心率、真实 ECG 准确率、延迟或 ADC 采集通过。

本地 `sim/tb_ecg_smoke.sv` 使用真实 AXI 写样本驱动实际检测器（不强制注入 qrs_valid），已验证同一组事件、正负能量与 FIFO 行为。PS 平台及应用已构建，板上执行尚待用户提供日志；本地仿真不能替代 PS→PL 实测。

### 复现构建

在项目根目录，用本机安装路径替换占位符：

```powershell
& '<Vitis安装目录>/bin/vitis.bat' -s board/build_ecg_smoke.py
./sim/run_ecg_smoke_test.ps1 -VivadoBin '<Vivado安装目录>/bin'
```

构建脚本默认读取 `releases/latest/ecg_system_candidate.xsa`；已有工作区时停止，避免覆盖。重建时用环境变量 ECG_SMOKE_WORKSPACE 指定新的空工作区，ECG_SMOKE_XSA 可显式选择匹配 XSA；仿真已有输出时用 OutputDir 参数选新的输出目录。正式源码修改后需要重新导入并构建，不能把 tmp 里的旧副本当最新版。

本轮证据：`tmp/ecg_smoke_build.log`、`tmp/ecg_smoke/rtl_check/simulation.log`、`tmp/ecg_smoke/artifacts.json`。构建/仿真通过后按本节运行；通过实测后再决定是否制作新的启动镜像与更新 latest。

## 21. 整数参考模型与 RTL 逐周期对照

**smoke 尚未上板测试。** 它目前只有应用构建和合成输入 RTL 仿真通过；本节的参考模型也不能替代 PS→AXI→检测器→FIFO 板上验收。Hello World 的板上成功不等于 ECG smoke 成功。

参考模型 `src/reference/ecg_reference.py` 用 Python 标准库实现当前 `ecg_qrs_detector.sv`，不是新的滤波或检测算法，也不模拟 AXI、FIFO、ADC 或真实心电准确率。默认 16 位有符号样本、360Hz、120ms（43点）、200ms（72点）、24位能量。保留位宽截断/回绕、整数右移、旧状态判断及同周期非阻塞更新语义。

### 输入输出

输入 CSV 至少有 `sample` 列，每行表示一个时钟周期；可选 `valid`、`reset_n`，默认均为 1。样本为已量化整数（默认 -32768..32767），不接受直接混入浮点毫伏。示例：

```csv
sample,valid,reset_n
0,0,0
0,1,1
0,1,1
20000,1,1
20000,0,1
0,1,1
```

`reset_n=0` 清状态，首个有效样本只建立上一采样；`valid=0` 不推进样本计数、积分或不应期，但 RTL 的阈值输出仍每时钟更新，事件 valid 清零。阈值上穿判断使用周期开始时的噪声/信号估计与旧不应期；不能先更新它们再判断事件。无新事件时位置和 RR 输出会保持，只有 qrs_valid=1 才登记新事件。

在项目根目录运行（Python 3.10 或更新版本，无需安装额外库）：

```powershell
python -B src/reference/ecg_reference.py --input '<输入CSV路径>' --output-dir tmp/reference_run
```

输出目录已有内容时停止避免覆盖。输出 `trace.csv` 是每周期状态，`events.csv` 是事件周期、近似位置和 RR 样本数，`summary.json` 保存参数/边界。需要其他参数可使用 `--sample-rate-hz`、`--integration-ms`、`--refractory-ms` 等；参数必须与目标 RTL 一致，不能把修改软件模型当作修改了板上配置。

程序接口（用 `python -B` 启动解释器，避免在正式源码目录生成字节码缓存）：

```python
from software.reference.ecg_reference import Config, Detector
model = Detector(Config())
model.tick(reset_n=False)
state = model.tick(sample=0, valid=True)
state = model.tick(sample=20000, valid=True)
print(state.integrated_energy, state.adaptive_threshold, state.qrs_valid)
```

本模型支持采样位宽 2..16、能量位宽 1..32，并检查参数乘积不溢出 RTL 的 32 位 integer。支持范围不等于所有参数组合都已验证。

### 对照验证

```powershell
python -B sim/check_ecg_reference.py --vivado-bin '<Vivado安装目录>/bin' --output-dir tmp/reference_check
```

检查脚本给真实 RTL 与 Python 同一批 reset/valid/sample 输入，逐周期比较 15 个字段：事件 valid/位置/RR、能量/阈值、噪声/信号估计、上一能量/样本/有效标志、采样计数、不应期、循环指针、上次位置及有效标志。失败时报告案例、周期、字段、RTL 值和模型值，输入、两侧 trace、日志保留在 tmp；不覆盖已有输出目录。

2026-10-14 六组对照全部通过，共 20915 个周期：

| 案例 | 周期数 | 目的 |
| --- | ---: | --- |
| smoke_waveform | 11722 | 16 个交替正负脉冲，含空拍；人工预期位置79+360×i，首次RR=0、后续360 |
| random_360 | 2403 | 默认参数、随机值/满量程、有效停顿、途中复位 |
| random_500 | 2403 | 500Hz参数、随机值、停顿、复位 |
| window_one_zero_levels | 1162 | 窗口/不应期最小长度1、初始估计0、阈值下限 |
| energy_wrap | 2403 | 12位能量回绕、噪声初值高于信号、随机值及复位 |
| noise_above_signal_32 | 822 | 32位复位表达式逻辑右移及噪声分支 |

证据在 `tmp/reference_check_20261014_01/report.json`，逐案例目录包含输入、RTL trace、Python trace 与比较记录。独立命令行运行 `tmp/reference_cli_20261014_01/` 的 trace/events 与对照脚本输出哈希一致。没有改 RTL 或发布镜像，没有使用板卡。

这些结果支持已测场景下模型与 RTL 一致，不代表所有状态的形式证明或真实数据准确率。下一步可准备有标注 ECG 整数数据，先跑模型定位误检/漏检，再让 RTL 回放同一数据；拿到板子后仍需先执行尚未上板的 smoke。

## 22. MIT-BIH 100 号记录离线基线（2026-10-15）

**smoke 尚未上板测试。** 本节只评估 Python 整数参考模型，没有运行真实 ECG 的 RTL 回放、修改检测器、写 Flash 或更新发布镜像。

数据来自 [MIT-BIH 1.0.0](https://physionet.org/content/mitdb/1.0.0/)，引用：Moody G, Mark R. MIT-BIH Arrhythmia Database, version 1.0.0, PhysioNet, DOI:10.13026/C2F305。仅下载 `100.hea`、`100.dat`、`100.atr` 和 `SHA256SUMS.txt`，原始文件保存在 `tmp/mitdb_100_20261015_01/raw/`；三项文件 SHA256 均与官方清单一致。

使用 MLII（第0通道），360Hz、650000点，时长1805.556秒。输入为数字 ADC 减去文件头基线1024，整数比例1，范围[-543,287]；不滤波、不重采样、不按标注归一化。文件头增益200 ADC单位/mV只用于画图。模型使用默认360Hz/120ms/200ms、24位能量、噪声4096/信号16384初值，每个有效样本后插入一个空拍，不推进样本位置。完整记录计分，不排除启动阶段。

解码依据 [WFDB format 212](https://physionet.org/physiotools/wag/signal-5.htm) 与 [MIT 标注格式](https://physionet.org/physiotools/wag/annot-5.htm)。除官方 SHA256 外，检查双通道首样本、采样数和文件头16位校验和；标注组成核对[官方100号说明](https://archive.physionet.org/physiobank/database/html/mitdbdir/records.htm)：N=2239、A=33、V=1，另1个节律标签不计为心搏。工具只支持已核查的100号格式，遇到不同组成会停止，不能直接当全库通用读取器。

评估采用固定±54点（150ms）有序一对一匹配，不作事后时间平移；这是本项目的初步离线统计规则，不是完整标准合规评估。结果：参考心搏2273、检出0、TP=0、FN=2273、FP=0，灵敏度0%、F1=0；由于没有检出事件，阳性预测值、定位误差及RR误差均无定义，不能写成0误差或100%精度。

已证实失败机制：43点差分绝对值窗口和最高1002，实际阈值最低4129（初始7168）。信号估计只在检出事件时更新，故全程维持16384，阈值无法降到输入能量范围；独立逐点重算窗口和与模型全部一致。此结论只适用于本次幅值映射和默认参数，不能推断所有幅值配置均失败。下一步应先明确输入幅值单位及启动期阈值校准方案，再用独立记录验证；本轮未实施算法修复。

复现（Python需有已安装的matplotlib用于图形输出，本次未安装依赖）：

```powershell
python -B sim/test_mitdb_100.py
python -B data/evaluate_mitdb_100.py --raw-dir tmp/mitdb_100_20261015_01/raw --output-dir tmp/mitdb_100_replay
```

输出目录必须不存在。完整核查结果在 `tmp/mitdb_100_20261015_01/baseline_verified/`：`summary.json` 为参数/指标/源码与数据哈希，`input.csv` 为模型输入，`reference_beats.csv` 为心搏标注，`events.csv` 为事件，`matches.csv`、`missed.csv`、`extra.csv` 为匹配/漏检/误检清单，`comparison.png` 为波形及能量/阈值对照。首次基线输出 `baseline/` 也保留，未覆盖删除。解析/匹配的三组单元测试通过。

## 23. 固定幅值与启动校准重跑（2026-10-15）

**smoke 仍未上板测试。** 本次仅修改离线输入与配置：新增 `src/reference/ecg_input.py`，评估工具增加 `--profile calibrated`，没有修改 `ecg_reference.py`、RTL、smoke、bitstream 或发布镜像。硬件目前不会自动执行本节幅值映射或校准，也没有增加运行时阈值寄存器。

幅值固定为4096整数单位/mV，按头文件200 ADC单位/mV及基线1024换算，采用正负对称四舍五入，超出16位时饱和并统计。本次范围[-11121,5878]，饱和点0。不使用全记录最大值或专家标注选择增益。

校准只读取最初720点（2秒），计算677个完整43点差分绝对值窗口和。排序后取下标floor((n-1)×0.5)及floor((n-1)×0.9)的值作为噪声/信号初值，下限分别为1及噪声+1；本次为1561/12475，初始阈值4289。先缓存这2秒，估计后重新初始化检测器并回放整个缓存及后续数据，因此包含2秒启动等待；开头2秒结果不能当作无等待的实时输出。校准不读取心搏位置，未按结果搜索参数；静默/高噪声启动和其他记录仍未验证。

采用与第22节相同的全记录±150ms一对一计分，无事后位置修正：

| 统计 | 原始幅值及默认初值 | 固定幅值及2秒校准 |
| --- | ---: | ---: |
| 参考心搏 | 2273 | 2273 |
| 检出事件 | 0 | 106 |
| 正确匹配TP | 0 | 44 |
| 漏检FN | 2273 | 2229 |
| 误检FP | 0 | 62 |
| 灵敏度 | 0% | 1.94% |
| 阳性预测值 | 无定义 | 41.51% |
| F1 | 0% | 3.70% |

仅评估2秒之后：参考2270、TP41/FN2229/FP62，灵敏度1.81%。44个匹配事件的平均绝对位置误差94.00ms；RR平均绝对误差3.17ms仅来自28个连续匹配间期，遗漏严重，不能据此宣称整体RR准确。

本次积分能量最高20522，阈值最低853，末尾信号/噪声估计933/827；650000点中640535点（约98.54%）能量不低于当时阈值。前10秒图可见触发，约913秒的示例中阈值低于背景能量，不能再形成正常的上穿。结合信号估计在首次上穿时采样、而非在能量峰值更新的源码机制，提示需要改进持续阈值更新及候选峰处理；本次没有扩大范围修改检测逻辑，也不证明单改某一行就能解决。

复现：

```powershell
python -B sim/test_mitdb_100.py
python -B data/evaluate_mitdb_100.py --raw-dir tmp/mitdb_100_20261015_01/raw --output-dir tmp/mitdb_100_calibrated --profile calibrated
```

结果在 `tmp/mitdb_100_20261015_01/calibrated_verified/`，日志 `calibrated_verified.log`；输入、事件、匹配和漏检误检CSV及PNG图均保留。`baseline_regression/` 重跑原配置仍为零事件。五组测试通过，新增检查幅值单位、正负舍入、饱和计数、校准只依赖前缀与短记录拒绝。独立窗口和逐点核对通过；本节仍是单记录离线开发结果，尚未完成真实波形RTL对照或多记录评估。

## 24. 候选峰软件原型与100号阶段检查

**smoke仍尚未上板测试。** `ecg_reference.py`继续作为旧RTL逐周期模型；新增`src/reference/ecg_peak_reference.py`是不同检测逻辑的软件原型，不能将此前旧模型的20915周期一致性结果用于这个原型。没有修改RTL、PS程序或发布文件。

保留4096单位/mV、前2秒无标注校准、43点积分及72点不应期。改动是：用能量局部峰启动候选，在固定21点确认期内保留最大能量峰，截止时间不随新峰延后；在确认后用峰能量更新信号估计，而非使用第一次上穿的低能量值。低于阈值的非不应期局部峰用于更新噪声。定位从该能量峰对应的43点原波形窗口中，选取偏离局部中位数最大的采样点，支持负向脉冲；检查定位后的不应期间隔，避免重复事件。软件只支持16位样本及能容纳完整窗口和的能量位宽，超出时拒绝，不声称具有RTL能量回绕行为。

默认、仅初始化修正、候选峰三组结果均保留，最新`--profile peak`全记录结果为：参考2273、检出2273、TP2272/FN1/FP1，灵敏度/阳性预测值/F1均99.9560%。匹配事件位置MAE1.4904ms，误差范围[-2.778,8.333]ms；2270个连续匹配RR区间的MAE1.5198ms。2秒校准段之后TP2269/FN1/FP1，灵敏度与阳性预测值99.9559%。标注N匹配2238/2239、A33/33、V1/1；这是位置检测，不是异常类型分类。

暂定单记录开发检查条件：灵敏度≥99%、阳性预测值≥99%、位置MAE≤10ms、连续匹配RR的MAE≤15ms，本次均达到。它是本项目当前开发检查，不是行业合规、临床验收或独立测试集结论；100号已参与开发，不能作为最终泛化证据。每5分钟分段统计也保存在报告中，前25分钟无误检漏检，25—30分钟误检1次，最后5.556秒漏检1次。

剩余问题完整计入评分：漏检采样点649991，距离记录结束仅9点（约25ms），没有继续输入确认候选；未补零或删除尾端标注。误检在583009点（1619.469秒），图中该处有额外振荡，未因已有高分继续按该位置调整算法。原型确认延迟实测为22.22—122.22ms、均值84.24ms（从估计心搏位置到事件输出的采样差）；这不是硬件实测运行延迟，也不含首次2秒校准缓存等待。

```powershell
python -B sim/test_ecg_peak_reference.py
python -B sim/test_mitdb_100.py
python -B data/evaluate_mitdb_100.py --raw-dir tmp/mitdb_100_20261015_01/raw --output-dir tmp/mitdb_100_peak --profile peak
```

最终结果在 `tmp/mitdb_100_20261015_01/peak_verified/`，日志`peak_verified.log`。包含全输入、事件、匹配/漏检/误检清单及波形图；summary记录源码/数据哈希、逐类型/逐时段统计、确认延迟与development_gate=PASS。9项单元测试通过，候选峰新增测试覆盖5000点静默、16个正负脉冲位置与RR、空拍/复位、不应期去重与样本越界。所有650000点的积分值均与独立窗口和核对一致。

原模型配置回归在 `peak_stage_baseline_regression/`（仍检出0）与`peak_stage_calibrated_regression/`（仍TP44/FN2229/FP62），旧失败记录未改写。下一阶段以固定方案开展多记录独立评估、RTL移植和逐周期对照；拿回板后仍需完成原smoke实测，不能跳过。
