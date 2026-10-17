# 数据与离线运行入口

本目录保留当前QRS评估、患者隔离CNN开发验证、数据获取及公共依赖。模型接手者先读[训练交接](../docs/model_training_handoff.md)，不要按版本号逐个启动旧实验。

## 当前文件

| 文件 | 用途 |
| --- | --- |
| download_mitdb_records.py / ecg_dataset.py | MIT获取、幅值读取和标注计分 |
| benchmark_qrs_v4.py / qrs_v4_protocol.json | 当前QRS及XQRS/GQRS对照 |
| plot_qrs_benchmark.py / profile_classification.py | 波形出图、分类数据盘点 |
| download_external_ecg.py | 外部数据库官方文件下载与校验 |
| prepare_cnn_expanded.py / extend_cnn_ltdb.py | 父缓存准备、公共切拍与历史RR函数 |
| cnn_expanded_v6_protocol.json / cnn_expanded_v7_protocol.json | 父缓存、来源和身份映射冻结依据 |
| prepare_cnn_cv.py / cnn_patient_cv_v8_protocol.json | 当前开发患者三折及缓存准备 |
| train_cnn_cv.py | 当前训练入口，不读取独立测试 |
| train_cnn_candidates.py / train_cnn_refined.py | 当前入口依赖的计分、损失、构建和增强；保留原文件名以维持冻结哈希，不是接手默认入口 |
| prepare_cnn_git.py / cnn_git_v1_protocol.json | Git克隆后直接下载/重建当前残差候选开发数据，无父缓存依赖 |
| requirements*.txt / results/ | 独立环境依赖及精选QRS摘要 |

src/reference/ecg_mf_cnn.py保留公共分类指标，ecg_trainable_cnn.py和ecg_temporal_cnn.py提供当前候选网络。旧文件名不表示无用；当前正式流程不导入tmp/history。

## QRS运行

从项目根目录执行，替换本机解释器路径，输出目录必须不存在：

```powershell
python -m venv tmp/qrs_env
& './tmp/qrs_env/Scripts/python.exe' -m pip install -r data/requirements_qrs.txt
& './tmp/qrs_env/Scripts/python.exe' -B data/download_mitdb_records.py --output-dir tmp/qrs_current/raw
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --stage development --output-dir tmp/qrs_current/development
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --stage evaluation --output-dir tmp/qrs_current/evaluation
```

MIT原始文件校验官方SHA256及212首值/长度/校验和，按MLII选导联。QRS采用360Hz、4096单位/mV和int16饱和，分类采用物理mV及独立切拍协议，两种幅值口径不可混用。

## CNN运行和归档

克隆后的数据下载、重建、训练与复核见[训练交接](../docs/model_training_handoff.md)，原始文件重建见[患者CV说明](../docs/cnn_patient_cv.md)。不要重新freeze覆盖已评估协议，不把已查看开发数据当新测试。

独立旧脚本/协议/测试保存在tmp/history/training_handoff_20261017/，原路径、新路径与逐文件SHA256见其中manifest.json；恢复规则见交接文档。原始数据、环境和全部旧训练结果仍在原tmp位置，文字记录仍留[docs/records](../docs/README.md)。
