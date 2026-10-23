# 研究26完整42条复测与采用结果（2026-10-23）

## 结论

2026-10-23 按用户要求，用同一 raw、原协议、原门槛从原码重跑研究26，作为当前采用结果：

- 开发集 **18/19**，原评估集 **23/23**，合计 **41/42**。
- 唯一失败：**105**（TP 2562 / FN 10 / FP 67，Se 99.6112%，PPV 97.4515%，V 41/41）。
- 总体：TP 96,777 / FN 133 / FP 154，Se **99.8628%**，PPV **99.8411%**，F1 0.998519，位置 MAE **2.825 ms**，RR MAE 2.565 ms。
- 与第 26 轮记录值一致；算法、协议、门槛、原始数据均未改。

采用范围：**已知 42 条开发集复现，不是独立测试，也不代表整体合格**。105 的噪声误检仍未解决；27/28 及后续门控尝试均未超过该结果，不再为 105 继续调阈值或加记录特例。

## 数据一致性

- 原始目录：`tmp/multi_record_20261016_01/raw`
- 42 条记录 × `hea/dat/atr`，共 126 个文件；官方 `SHA256SUMS.txt` 校验通过。
- 与旧 42 条运行的 `source_sha256` 逐文件比对：**0 个不一致**。
- 每条 650000 点；本次未使用今天新增的 NST 噪声数据。

## 复现命令

```powershell
python -B data/benchmark_qrs_research.py --raw-dir tmp/multi_record_20261016_01/raw --output-dir tmp/qrs_research26_rerun_20261023/development --stage development
python -B data/benchmark_qrs_research.py --raw-dir tmp/multi_record_20261016_01/raw --output-dir tmp/qrs_research26_rerun_20261023/evaluation --stage evaluation
```

## 证据

- 固化结果：[data/results/qrs_research26_20261023.json](../../data/results/qrs_research26_20261023.json)
- 开发集摘要：`tmp/qrs_research26_rerun_20261023/development/summary.json`
- 评估集摘要：`tmp/qrs_research26_rerun_20261023/evaluation/summary.json`
- 运行日志：同目录 `development.log`、`evaluation.log`
- 协议：`data/qrs_research_protocol.json`
- 源码：`src/reference/qrs_research/`

## 限制与边界

- 42 条全部已查看，只能称已知开发集复现；不能重划后称独立测试。
- 单导联 MLII、360Hz、4096 单位/mV；未覆盖起搏、室扑、500Hz、ADS1292R 真实前端。
- 105 是真实高噪声记录，67 个 FP、10 个 FN 集中在噪声段；这是算法噪声鲁棒性不足，不是数据损坏。
- 完整在线运行时、因果/内存边界、整数 PS/PL、匹配镜像与上板仍未验证。

## 未做

未修改研究26源码/参数/门槛，未替换正式 v5，未写 Flash/操作板卡，未训练 CNN，未执行 Git 提交。
