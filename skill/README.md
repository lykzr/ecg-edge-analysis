# 可复用 FPGA 工程技能包

本包按 AMD 自主选题指南 3.3.5.2 整理，面向陌生队伍及 AI 助手。提炼自软硬件比对、下载排障、CNN 并行优化与交接实践，适用于推理、滤波、通信、控制等工程。**只复制 `skill/` 即可运行自检，不依赖心电工程、原作者盘符、工具缓存或聊天上下文。**

## 技能索引

| 技能与入口 | 适用场景与使用方法 | 观察来源与已验证效果 | 失效条件 |
| --- | --- | --- | --- |
| [交付文件校验](artifact-check/SKILL.md) | 按可信清单核对字节数和 SHA256；运行 `check_files.py` | Git 换行曾改变原始产物；独立测试覆盖篡改、缺失、换行和路径越界 | 文件与清单同时被替换无法识别；相同字节不证明启动成功 |
| [黄金参考比对](trace-check/SKILL.md) | 软件/RTL 导出同序号 CSV；运行 `compare_csv.py`，预先固定容差 | 来自逐周期状态、符号与舍入排障；测试精确整数、大整数、键错位、容差和非有限值 | 参考也可能错误；不自动对齐，不代替专家准确率 |
| [下载与启动诊断](download-diagnose/SKILL.md) | 按现象表逐层检查工具、目标、镜像、运行与冷启动 | 来自临时目录、服务器生命周期、串口占用及回供电观察；每次只认可已取得的证据 | 参数须取自本队板卡资料；新板卡/冷启动须另验 |
| [Vivado 资源与时序核查](vivado-report-check/SKILL.md) | 导出配对报告，运行 `check_reports.py`，传入器件/时钟/预算 | 真实 2026.1 实现报告解析出 122.5 BRAM36；正裕量下仍发现 1 项输出延迟告警，默认拒绝通过 | 仅支持已测试英文布局；不读取 DRC，不代表动态负载 |
| [公平计时与优化评估](acceleration-review/SKILL.md) | 填实验合同，数值核对后运行 `summarize_pairs.py`，用总时间之比 | 来自 ROM 复制、并行度和计时口径纠错；复算既有 72 拍流式记录，另核对整段聚合计时 | 信任提供的哈希、计时和配对；不一致不输出有效倍率；不是吞吐/功耗测试 |

每项 `SKILL.md` 都包含适用、使用、失败来源、验证和失效边界。包含可执行校验脚本、提示词工作流、[实验/报告模板](acceleration-review/assets/experiment.md)及结构化排障表。提示词是事后提炼的复用模板，**不能冒充原始大模型协作记录**。

## 陌生队伍快速使用

需要 Python 3.10+，全部执行脚本和测试只用标准库。解压/复制到含空格路径也可以；命令中的输入文件路径须替换为自己工程的真实数据。

在复制后的 `skill/` 内执行：

```text
python -B -m unittest discover -s tests -p "test_*.py"
python -B artifact-check/scripts/check_files.py --root <文件目录> --manifest <清单JSON>
python -B trace-check/scripts/compare_csv.py --reference golden.csv --candidate actual.csv --key cycle
python -B vivado-report-check/scripts/check_reports.py --utilization utilization.rpt --timing timing.rpt --clock <时钟名> --period-ns <周期ns> --budget vivado-report-check/examples/budget.json
python -B acceleration-review/scripts/summarize_pairs.py --pairs acceleration-review/assets/example_pairs.csv --metadata acceleration-review/assets/example_metadata.json
```

最后一条是**合成示例**，累计倍率约 1.818，不是板测成绩。预算 JSON 同样仅为示例，应先于实验冻结实际预算。脚本通过退出 0，失败退出 1，输出 JSON；输入文件只读。JSON 使用 ASCII 转义，避免 Windows 默认 GBK 与 UTF-8 读取不一致。

也可以只复制一个技能子目录以及本包 LICENSE；它不导入其他技能。测试目录用于整包自检，故整包自检需保留全部五项。在 AI 工具中可手动让助手读取对应 `SKILL.md`；比赛提交不要求安装插件。

## 推荐复用流程

1. 用实验模板冻结输入、模型/算法、精度、状态、计时范围、容差和资源预算。
2. 验证交付文件，并比对独立参考；失败保留原始数据和首个差异。
3. 核对 Routed 报告，分开记录时序裕量、约束覆盖与资源，不用 HLS 估计替代实现报告。
4. 获得板测计时后累计配对，分别说明核计算、调用含传输和端到端延迟。优化前后保持可比较条件。
5. 下载问题按诊断表分层，区分 READY、实际负载、Flash Verify 与彻底断电启动。

## 验证证据与边界

[validation.json](validation.json) 记录本轮测试、脚本与来源证据 SHA256、实际报告解析及历史计时复算。本轮没有新综合、实现、下载、Flash 写入或训练，也没有打开串口或停止网页。

已验证 Windows/Python、复制到独立含空格目录、从另一工程工作目录运行。未验证 Linux/macOS、第二板卡或所有 Vivado 版本；`export_reports.tcl` 是未在本轮 Vivado 执行的操作模板。报告解析不修改已有证据。历史工程效果不自动成为其他队伍的效果。

本工程采用裸机 ARM + PL，**没有验证 PYNQ Overlay/DMA，本包不主张通用 PYNQ Skill 加分**。可移植的报告/文件/计时工具也可用于 PYNQ 工程的离线环节，但不能据此声称完成 PYNQ 上板验证。

包内自有代码采用 [MIT License](LICENSE)。外部工程、工具、IP、数据和模型须分别核对许可；本许可不授予它们的再分发权。
