# 基于 Zynq-7020 的心电边缘分析项目

本目录是统一项目根目录，目标板为**正点原子领航者 V2 的 7020 核心板**，器件 `xc7z020clg400-2`。核心板/底板实物版本仍需核实。当前实现是 QRS 候选检测和 PS 通过 AXI-Lite 送样本的硬件框架。

## 目录

- `src/rtl/`：检测器和 AXI-Lite 事件 FIFO。
- `build/`：领航者配置和完整工程创建 Tcl 脚本。
- `sim/`：可复用接口自检。
- `src/ps/ecg_smoke/main.c`：PS 受控样本自检，检查配置、事件字段和 FIFO，运行方式见[下载教程](board/download_guide.md#20-ps-读取配置与受控样本fifo-自检)。
- `src/reference/ecg_reference.py`：当前检测器的逐周期整数参考模型，CSV 使用和 RTL 对照见[教程](board/download_guide.md#21-整数参考模型与-rtl-逐周期对照)。
- `vivado/ecg_edge/ecg_edge.xpr`：历史工程，可能引用迁移前路径；后续从 build/ 脚本新建工程，不以旧工程为源码入口。
- `board/`：PS smoke 构建脚本与下载教程；已生成的本机 smoke 工作区仍在 tmp/，可按原 Run 配置使用。
- `data/`：数据获取/评估脚本、来源说明与精选离线结果。
- `skill/`：已验证经验的复用流程、用法及失效边界。
- `report/`：项目计划及尚待完成的报告交付项。
- `docs/`：寄存器说明与资料索引；完整历史过程留在本地忽略的 lykzr.md。
- `tmp/`：构建工程、缓存、日志、备份和待验证产物；不自动清空。
- `releases/latest/`：当前发布镜像和配套文件，见 [烧录说明与验证范围](releases/latest/README.md)。历史版本留在本地并被忽略，不删除；[归档约定](releases/README.md)。

[项目计划与待办](report/project_plan.md) · [寄存器接口](docs/register_map.md) · [资料说明](docs/materials_review.md) · [数据与结果](data/README.md) · [可复用流程](skill/README.md)

采用指南3.3.5.4推荐的 src/sim/build/board/data/skill/report 主结构；额外 docs/ 保存接口和资料索引，releases/latest/ 保存当前确认交付。该结构下 build/ 是源码脚本目录，工具的构建工程与缓存仍统一写入 tmp/。所有命令默认从项目根运行。迁移前后的路径对照及尚未完成的交付项在计划第9节；现有 tmp/、vivado/、发布清单保留历史路径，不批量改写历史证据。

项目自有代码和文档采用 [MIT许可证](LICENSE)，第三方数据/工具生成代码/手册另见 [来源与许可边界](third_party.md)。添加许可证不代表仓库已上传或公开；Git仍暂停。PDF指南与板卡手册不随本项目MIT许可重新授权。

[Zynq 下载与串口通用教程](board/download_guide.md)：包含 Vivado/Vitis 操作、独立工作区、平台与应用构建、Run 初始化及 QSPI 固化。QSPI 测试产物在 `tmp/qspi_boot_20261013_01/`，旧 JTAG 示例工作区保留在 `tmp/vitis_bringup/`。

## 领航者配置

板级依据为配套 Vitis 指南第 2 章和官方 7020 Hello World 例程：PS 输入 33.333333 MHz，32 位低电压 DDR3、兼容配置型号 `MT41K256M16 RE-125`、DDR 533.333333 MHz；板载串口为 UART0/MIO14–15。这个 DDR 型号是 Vivado 兼容配置，不能当作实物丝印。

PL 启用 100 MHz FCLK0、GP0 AXI 和复位控制器。ECG 基地址为 `0x43C00000`，完整寄存器定义见 [register_map.md](docs/register_map.md)。事件 FIFO 默认深度 8；先读队首的索引、RR、序号，再写状态 bit0 弹出。满队列保留已有事件、报告溢出及累计丢弃数。

在已打开的 Vivado 工程中执行：

```tcl
# 必须按实际 ECG 数据采样率设置，默认 360 Hz。
set ecg_sample_rate_hz 360
source {<ecg_edge项目根目录>/build/build_navigator_ecg_system.tcl}
```

将尖括号占位符替换成实际项目根目录；脚本本身按自己的位置定位源码，不依赖工程放在 `vivado/` 还是 `tmp/`。

旧名称 `build_ac7020_ecg_system.tcl` 和 `configure_ac7020_ps.tcl` 仅转发到领航者脚本，不再应用 AC7020 配置。构建脚本会创建或更新 PS7/ECG BD、验证、生成 wrapper/IP 输出；不自动综合、实现或烧录。

## 从空目录重建

在项目根目录运行，替换 Vivado 安装路径：

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/create_rtl_project.tcl -tclargs xc7z020clg400-2
```

新工程放 `tmp/vivado/ecg_edge`，已有同名目录时脚本停止以免覆盖。脚本添加 RTL，创建完整 PS7/AXI BD，设置 wrapper 顶层并验证；不把生成物当作源代码提交。

## RTL 自检

```powershell
./sim/run_rtl_tests.ps1 -VivadoBin '<Vivado安装目录>/bin'
```

日志和波形默认在 `tmp/rtl_tests/`，已有目录时用 `-OutputDir` 指定新的位置，避免覆盖历史。测试覆盖 AW/W 分开到达、响应反压、零 WSTRB、事件 FIFO 快照、溢出及同周期出入队、非法/未对齐地址和采样率参数。测试用例包含合成数据及受控事件，不代表真实 ECG 准确率或完整 AXI 认证。

## 验证边界

10 月 6 日旧 bitstream 早于领航者修复，不能继续作为新版输出。10 月 13 日的 JTAG 候选版本已记录 RTL 自检、BD 验证、整机综合/实现、bitstream 生成及 XSA 导出通过，证据在 `tmp/pre_download_20261013_01/`；用户也提供了 Hello World 板上串口输出。具体环境、产物和各阶段边界见 [工程过程记录](lykzr.md)。Vitis 工作区迁移后尚未再次上板验证，ECG 寄存器读写、真实心电输入与标注准确率仍未验证；QSPI 自启动另行验收。

**ECG smoke 尚未上板测试**：只完成应用构建及合成样本 RTL 仿真，不能视为 PS→AXI→检测器→FIFO 板上验证通过。当前整数参考模型已实现，并通过六组、20915 个周期的 RTL 状态对照；这不代表真实 ECG 检测准确率通过。

2026-10-15 已完成 MIT-BIH 100 号 MLII 全记录的默认参数离线基线：650000 点、2273 个标注心搏，检出 0 个。原始整数幅值下积分能量最高1002，阈值最低4129，默认初始信号估计无法启动检测；这是一项失败基线，不是准确率验收通过。可复现工具为 `data/evaluate_mitdb_100.py`，详细方法与结果见下载教程第22节。

同日增加离线幅值映射（4096整数单位/mV）与前2秒无标注校准：100号全记录正确匹配44、漏检2229、误检62，灵敏度1.94%，仍未达到可用检测效果。阈值后续降低到背景能量以下，单改初始化不足以解决问题；详见下载教程第23节。输入/校准尚未移植PS/RTL，原检测器及smoke保持不变。

随后新增 `src/reference/ecg_peak_reference.py` 候选峰软件原型：100号全记录TP2272/FN1/FP1，灵敏度与阳性预测值均99.956%，位置平均绝对误差1.490ms，达到本阶段暂定的单记录开发检查要求。它按确认后的峰值更新信号估计，并在原波形窗口定位极值；**不是现有RTL的逐周期模型，尚未移植RTL或上板**。误检/漏检及延迟说明见下载教程第24节。

尚需完成 smoke 上板验收、多记录独立 ECG 评估、候选峰算法RTL移植与一致性验证、浮点滤波基准、带通/基线处理、信号质量评估以及 AFE/ADC 接入。硬件框架不会仅凭下载 bitstream 自动采集心电。采样率、幅值和模拟前端仍需确认。

Git 操作继续暂停。`.gitignore` 只影响未来未跟踪文件的选择，不能自动移除已经跟踪的生成物；本轮没有操作索引、提交、远端或 `.git`。
