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



## 已选开发基线复核



[baseline/](baseline/README.md)保留已选residual_verified三折权重、归一化、预测/指标及冻结协议，用sim/check_baseline.py核验；它是失败开发对照，不是最终模型。先用标准库核对哈希，再用NumPy重算指标，按Git入口重建开发缓存后可用Torch重放，不重新训练、不读独立测试。



cnn_mf_v1/context_v4/trainable_v2/refined_v3四份协议仍被正式公共脚本的旧入口引用，故保留原字节以免默认路径缺失；它们不是推荐的新训练入口。完整旧实验数据准备/历史专用代码仍可能在tmp/history，接手新任务使用prepare_cnn_git.py；不能把四个协议存在解释成全部历史都已可从空目录复跑。



## 实际CSV输入诊断



python -B data/analyze_capture.py --source <五列RawData.csv> --output tmp/capture_analysis_new。保持现有原检测器参数，核对CH2/shift8、独立滑动差分能量、因果带通/50Hz陷波和阈值；保存完整启动/尾部，不用无标注CSV声称检出率，不修改板端。



## 原检测器启动候选回归

evaluate_qrs_auto.py复用qrs_v4_protocol.json的19条已知开发记录，比较原整数检测器和独立启动/峰判决候选，输出逐记录、类型、时间块及全部错漏位置。它不修改原协议，不读未触碰评估集，不恢复CNN训练。来源、原生ADC码与预热计分方式见[候选说明](../docs/qrs_auto.md)，派生结果保存到新tmp目录。


## 原波形定位与质量确认

evaluate_qrs_peak.py复用同一19条开发记录和官方校验，读取上一轮auto基线逐记录JSON做同输入比较，保存类型/时间块、全部错漏和确认等待。原始数据与派生产物仍在tmp，操作见[说明](../docs/qrs_peak.md)。它只评估独立软件，不读取新独立测试或运行CNN，不修改原v4基线及冻结协议。


## 成熟QRS独立候选

benchmark_qrs_v5.py和qrs_v5_protocol.json用于360Hz/4096单位每mV的完整已知记录回归；原v4协议不改。入口核对冻结依赖及原记录/幅值/容差/门槛，输出类型/时间块、全部事件/错漏/RR和确认等待。development/evaluation均为已查看数据，不称新独立测试。命令与部署边界见[说明](../docs/qrs_v5.md)。


## 未合格研究快照便携复现

benchmark_qrs_research.py从同一原码重建研究26，不依赖本机tmp事件CSV；协议明确已知开发回归。原历史协议不改写，输入需自行取得并校验，输出必须指定新目录。方法和未验边界见[说明](../docs/qrs_research.md)，评估顺序见[计划](../report/evaluation_plan.md)。
