# 基于 Zynq-7020 的心电边缘分析项目

本目录是统一项目根目录，目标板为**正点原子领航者 V2 的 7020 核心板**，器件 `xc7z020clg400-2`。核心板/底板实物版本仍需核实。当前实现是 QRS 候选检测和 PS 通过 AXI-Lite 送样本的硬件框架。

## 目录

- `rtl/`：检测器和 AXI-Lite 事件 FIFO。
- `scripts/`：领航者配置、完整工程创建和 RTL 自检脚本。
- `tests/`：可复用接口自检。
- `vivado/ecg_edge/ecg_edge.xpr`：现有 Vivado 工程。
- `docs/`：项目计划、寄存器说明、资料说明和迁移记录。
- `docs/reference/`：本地参考 PDF，默认不纳入公开交付。
- `tmp/`：备份、资料索引、日志、波形和临时构建，全部忽略。

[项目计划](docs/project_plan.md) · [寄存器接口](docs/register_map.md) · [资料说明](docs/materials_review.md) · [迁移记录](docs/workspace_migration.md)

## 领航者配置

板级依据为配套 Vitis 指南第 2 章和官方 7020 Hello World 例程：PS 输入 33.333333 MHz，32 位低电压 DDR3、兼容配置型号 `MT41K256M16 RE-125`、DDR 533.333333 MHz；板载串口为 UART0/MIO14–15。这个 DDR 型号是 Vivado 兼容配置，不能当作实物丝印。

PL 启用 100 MHz FCLK0、GP0 AXI 和复位控制器。ECG 基地址为 `0x43C00000`，完整寄存器定义见 [register_map.md](docs/register_map.md)。事件 FIFO 默认深度 8；先读队首的索引、RR、序号，再写状态 bit0 弹出。满队列保留已有事件、报告溢出及累计丢弃数。

在已打开的 Vivado 工程中执行：

```tcl
# 必须按实际 ECG 数据采样率设置，默认 360 Hz。
set ecg_sample_rate_hz 360
source {<ecg_edge项目根目录>/scripts/build_navigator_ecg_system.tcl}
```

将尖括号占位符替换成实际项目根目录；脚本本身按自己的位置定位源码，不依赖工程放在 `vivado/` 还是 `tmp/`。

旧名称 `build_ac7020_ecg_system.tcl` 和 `configure_ac7020_ps.tcl` 仅转发到领航者脚本，不再应用 AC7020 配置。构建脚本会创建或更新 PS7/ECG BD、验证、生成 wrapper/IP 输出；不自动综合、实现或烧录。

## 从空目录重建

在项目根目录运行，替换 Vivado 安装路径：

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source scripts/create_rtl_project.tcl -tclargs xc7z020clg400-2
```

新工程放 `tmp/vivado/ecg_edge`，已有同名目录时脚本停止以免覆盖。脚本添加 RTL，创建完整 PS7/AXI BD，设置 wrapper 顶层并验证；不把生成物当作源代码提交。

## RTL 自检

```powershell
./scripts/run_rtl_tests.ps1 -VivadoBin '<Vivado安装目录>/bin'
```

日志和波形在 `tmp/rtl_tests/`。测试覆盖 AW/W 分开到达、响应反压、零 WSTRB、事件 FIFO 快照、溢出及同周期出入队、非法/未对齐地址和采样率参数。测试用例包含合成数据及受控事件，不代表真实 ECG 准确率或完整 AXI 认证。

## 验证边界

修复前的综合/实现/bitstream 已存在，但来自旧配置，不能继续视为领航者可用结果。修复后的 RTL 自检已经通过；当前 BD 的验证结果及修复后综合结果见 [迁移与验证记录](docs/workspace_migration.md)。没有执行下载、上板、真实心电输入或标注数据准确率验证。

尚需完成 PS/Vitis 样本回放应用和平台、软件参考模型、带通/基线处理、信号质量评估以及 AFE/ADC 接入。硬件框架不会仅凭下载 bitstream 自动采集心电。采样率、幅值和模拟前端仍需确认。

Git 操作继续暂停。`.gitignore` 只影响未来未跟踪文件的选择，不能自动移除已经跟踪的生成物；本轮没有操作索引、提交、远端或 `.git`。
