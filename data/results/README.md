# 精选100号结果与生成信息

以下JSON只保存统计/参数/数据与代码哈希，不包含原始ECG波形或标注文件。

| 文件 | 来源与状态 |
| --- | --- |
| record_100_baseline.json | 目录迁移前默认配置失败基线，保持原始字节/哈希路径 |
| record_100_calibrated.json | 迁移前幅值/初始化修正结果，TP44/FN2229/FP62 |
| record_100_peak.json | 迁移前候选峰结果，TP2272/FN1/FP1 |
| record_100_peak_layout.json | 迁移后用data/evaluate_mitdb_100.py重跑，相同数据及参数，结果相同，源码路径/哈希为新布局 |

历史摘要中的scripts/、software/路径是当时来源，不改写成新路径后冒充原快照。当前新路径对照在report/project_plan.md第9.1节；迁移前文件内容可通过本机tmp/backup/layout_20261015_01快照定位。

本机完整新回放目录：tmp/layout_check_20261015_01/record_100_peak/，包含输入、参考心搏、匹配、漏检、误检和图片，未复制整个缓存。原始文件校验、全650000点独立积分核对通过。原始数据仍可用data/download_mitdb_100.py获取，下载和计分过程见上级README。

smoke仍未上板；候选峰原型还没有RTL实现。此处PASS只指100号单记录离线开发检查。
