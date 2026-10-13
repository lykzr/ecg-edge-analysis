# 工作区归并与工程修复记录

日期：2026-10-13。

## 统一项目根目录

`C:/Users/23006/Desktop/fpga/ecg_edge` 是现有仓库及统一项目根目录，外层 `Desktop/fpga` 只保留此目录。没有执行 Git 命令，没有暂存、提交、推送或修改 `.git`。没有迁移或修改 `Desktop/VHDL` 的内容。

| 原外层内容 | 新位置 |
| --- | --- |
| `AGENTS.md` | 项目根目录 `AGENTS.md` |
| `baidu_netdisk_review.md` | `docs/materials_review.md` |
| `tmp/` | 项目根目录 `tmp/`，含备份、审查报告、索引、脚本和预览 |
| AMD 2026 选题指南 PDF | `docs/reference/amd_track_guide_2026.pdf` |
| Vitis 2026.1 中文手册 PDF | `docs/reference/vitis_embedded_2026_1_zh.pdf` |
| 根目录 `.Xil`、`vivado.jou` | `tmp/legacy_vivado/` |

原始文件采用移动，没有删除。`ecg_edge/vivado/ecg_edge` 原有工程目录保持原位置，避免破坏 Vivado 相对路径。A 盘下载资料仍在原来的 D 盘目录，没有把整个资料盘塞进仓库。

## 忽略范围

`.gitignore` 排除项目 `tmp/`、Vivado 缓存/生成/运行目录、bitstream/XSA/ELF、中间网表、日志和波形、本机 IDE、Python/Node 环境及本地凭证。`docs/reference/` 是本地第三方资料，也默认忽略。

正式 RTL、测试、Tcl/PowerShell 构建脚本、README、项目计划、寄存器接口、XPR/BD/XCI 等保留为项目文件。忽略规则不能从 Git 历史或现有索引中自动移除文件，本轮未操作这些状态。

## 修复内容

1. 现有 BD 与新构建脚本改为 UART0/MIO14–15，关闭 UART1；DDR 改为 `DDR 3 (Low Voltage)` 和兼容配置 `MT41K256M16 RE-125`。
2. `build_navigator_ecg_system.tcl` 负责领航者配置。旧 AC7020 名称脚本仅作兼容入口，转发到新脚本。
3. 构建脚本可从没有 BD 的新工程创建 PS7/AXI/ECG 完整系统；按脚本自身路径定位源码，支持现有工程和 tmp 内新工程。
4. 刷新 RTL 模块使用项目 IP 对象；刷新后重新获取 BD 对象，避免沿用失效句柄。此行为经 Vivado 2026.1 实际运行核实。
5. QRS 事件保存到默认 8 深度 FIFO，位置/RR/序号保持同一事件的快照；队列满时保留已有事件，显式记录溢出及丢弃数。
6. 解码完整地址，未实现、未对齐或向只读地址写入返回 SLVERR，没有低 6 位地址镜像副作用。
7. AXI 包装层传入采样率/积分窗口/不应期参数，增加只读参数寄存器；RR 使用与事件位置一致的非负回移索引计算。
8. 新增正式接口自检 `tests/tb_axi_lite.sv` 和 `scripts/run_rtl_tests.ps1`。详见 [寄存器说明](register_map.md)。

## 验证结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| RTL 行为自检 | 通过 | `tmp/rtl_tests/xsim.log` 的 PASS 标志 |
| AW/W 分开、响应反压、零写选通 | 通过 | 上述自检 |
| 事件快照、FIFO 满溢出、同时出入队、序号 | 通过 | 上述自检，测试深度 2，包含受控事件注入 |
| 非法/未对齐地址没有采样副作用 | 通过 | 上述自检 |
| 参数采样率 500 Hz 传入并可读回 | 通过 | 上述自检；正式 BD 默认仍为 360 Hz |
| 实际现有 BD 配置与验证 | 通过 | `tmp/validate_navigator.log`；保存 BD 的 validated=true，UART/DDR 值已核查 |
| 从空目录创建完整工程 | 通过 | `tmp/rebuild.log`；工程在 `tmp/vivado/ecg_edge` |
| ECG RTL 独立综合 | 通过 | `tmp/rtl_synth.log` 的 `ECG_RTL_SYNTH_PASS`；0 Errors、0 Critical Warnings |

Vivado 仍有 SystemVerilog 模块打包支持、内部 localparam 依赖分析和未使用信号等警告；这些没有阻止本次验证和独立综合，不等于所有警告已消除。

没有做修复后整个系统的实现/时序收敛、新 bitstream 生成、XSA 导出、PS 应用构建、下载或板上运行。原 `.runs/impl_1` 中的 bitstream 是旧配置，不能当作修复后的输出使用。独立 RTL 综合不代表整机时序通过，合成样本/事件测试不代表真实心电检测准确率。

## 备份和剩余工作

修改前的 RTL、脚本、README、忽略文件、XPR、BD 保存在 `tmp/backup/ecg_before_navigator_fix_20261013/`。核查报告在 `tmp/engineering_audit/report.md`，它描述修复前状态。

下一阶段仍需核实实物核心板/底板版本及实际采样率，重建整机结果和硬件平台，完成 PS 样本回放程序与软件参考模型，再验证真实 ECG 数据和采集前端。Git 继续暂停，直到用户明确恢复。
