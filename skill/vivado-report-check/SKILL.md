---
name: vivado-report-check
description: 只读核查Vivado资源与时序文本报告，区分裕量通过、约束缺失和资源预算，输出可追溯JSON。
---

# Vivado 资源与时序核查

适用：有同一设计的 `report_utilization` 与 `report_timing_summary` 英文文本报告，准备比较 FPGA 优化版本或验收实现结果。Python 3.10+ 标准库，无需安装 Vivado 即可读取报告；不依赖心电、特定板卡或原作者路径。

## 使用步骤

1. 从实际打开的设计导出配对报告，保留原文件，不用手填数据替代。可参考 [导出 Tcl](scripts/export_reports.tcl)，它只导出当前打开的实现，不打开/重建工程、不连接板卡。本轮未在 Vivado 执行该 Tcl 模板；实际执行验证的是 Python 报告核查。
2. 先冻结目标器件、时钟周期与资源预算，再执行脚本。预算示例见 [budget.json](examples/budget.json)，其中百分数是演示阈值，须按自己的约束修改。

```text
python scripts/check_reports.py --utilization utilization.rpt --timing timing.rpt --device xc7z020clg400-2 --clock clk_fpga_0 --period-ns 10 --budget examples/budget.json
```

路径相对当前工作目录。JSON 输出包含输入 SHA256、设计/工具身份、资源、时钟、WNS/WHS/脉宽、失败端点与约束检查。退出 0 表示通过本次明确检查；退出 1 包括超预算、负裕量、非零违例、约束检查非零、字段缺失或不支持的格式。`passed=false` 不一定意味着逻辑功能错误，应先看 errors。

3. 对 `no_output_delay` 等非零项定位到具体引脚、外部时序需求和 XDC。脚本默认阻断，不静默忽略。本例 `examples/budget.json` 不豁免任何告警。若工程负责人已审核并明确接受某项数量，可在一次命令中写明：

```text
python scripts/check_reports.py --utilization utilization.rpt --timing timing.rpt --clock clk_fpga_0 --period-ns 10 --reviewed-check no_output_delay=1 --review-note "已核实为异步状态LED，无外部同步采样要求；接受1项输出延迟告警"
```

此处仅演示审核说明格式，不能代替自己核验。只有名称和数量均精确匹配才接受；缺少说明、未知检查名或数量变化仍失败。JSON 保留全部告警和审核内容，`constraints_clean` 仍为 false。不修改 XDC，不加 false path 掩盖问题。

## 从哪些观察提炼

并行化曾造成共享 ROM 复制、BRAM 上升；必须看实现后的整系统和层级资源，不能只引用 HLS 估计。后来将权重映射 LUTRAM，以更多 LUT/DSP 换 BRAM 与速度。另一次核查发现 WNS/WHS 为正，但 `checking no_output_delay (1)` 仍存在，说明“已约束路径满足时序”不等于“约束完整”。本工具把两者分开。

## 已验证效果

随包测试覆盖通过、负建立/保持/脉宽裕量、缺失时钟、漏约束、预算、损坏格式、设计身份不一致和显式审核。项目的 Vivado 2026.1 Routed 报告可提取 LUT=28626、FF=20458、BRAM36=122.5、DSP=105、WNS=0.102ns、WHS=0.036ns；默认如实拒绝该报告的 1 项 `no_output_delay`。见 [包级验证](../validation.json)，测试仅解析原报告，不声称重新实现或板测。

## 失效条件

- 只支持当前已测试的英文文本布局；未知行名/字段、截断报告、部分数字缺失均停止，不把缺值当零。已验证 Vivado 2026.1 的 7 Series 报告，其他系列/版本应先用随包测试并人工核查。
- 不读取 DRC 报告；不能把通过说成“DRC零错误”。`report_methodology` 中缓存告警可能过时，应重新导出并核查。
- 配对设计名/工具版本/实现状态与输入哈希可查，但不能从两份文本证明来自同一 BIT；另以产物清单绑定 BIT/XSA/DCP/报告。
- 静态资源不等于运行负载/功耗。层级资源分摊、HLS 估计、板上运行与算法准确率另验。
