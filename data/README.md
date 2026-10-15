# 数据与离线结果

数据集为 [MIT-BIH Arrhythmia Database 1.0.0](https://physionet.org/content/mitdb/1.0.0/)。目前仅100号参与开发，不作为独立测试集；尚未冻结多记录划分。原始文件不提交到正式目录；来源与许可边界见[第三方说明](../third_party.md)。

## 从零获取和运行

Python 3.14与matplotlib 3.10.9是本机已验证环境，matplotlib仅用于出图；读取、校准及检测实现使用标准库。依赖版本在requirements.txt，需要时在自己的环境执行`python -m pip install -r data/requirements.txt`；本次没有安装软件。其他Python版本尚未验证。Vivado/Vitis 2026.1仅用于硬件/PS构建，不用于本节离线回放。

在项目根目录运行（已有原始文件时仅校验，不覆盖；网络受限时先完成下载）：

```powershell
python -B data/download_mitdb_100.py
python -B sim/test_mitdb_100.py
python -B sim/test_ecg_peak_reference.py
python -B data/evaluate_mitdb_100.py --raw-dir tmp/mitdb_100/raw --output-dir tmp/mitdb_100/peak --profile peak
```

输出目录必须尚不存在。`baseline`、`calibrated`、`peak`分别为原始整数默认配置、固定幅值及2秒初始化、候选峰原型；默认仍为baseline，避免把不同算法混为一次结果。

## 当前证据

`results/`保存精选summary和生成信息，不复制完整缓存或数据集。2026-10-15结果：

| 配置 | TP | FN | FP | 灵敏度 |
| --- | ---: | ---: | ---: | ---: |
| baseline | 0 | 2273 | 0 | 0% |
| calibrated | 44 | 2229 | 62 | 1.94% |
| peak | 2272 | 1 | 1 | 99.956% |

完整650000点、约30分钟，不删除末尾漏检；固定±150ms有序一对一匹配。peak的位置MAE1.490ms、连续匹配RR MAE1.520ms；校准缓存最初2秒，新算法未移植RTL，smoke尚未上板测试。100号上本阶段暂定检查通过不代表临床、独立数据或板上验收。

精选JSON保留当时的源文件路径与哈希。目录迁移不改写历史哈希；请按[生成说明](results/README.md)区分旧路径历史结果与迁移后复核结果。后续数据划分、跨记录/噪声实验、最终数据再分发许可核查均见[计划](../report/project_plan.md)。
