# 数据与 QRS 离线入口

本目录只保留 **QRS 评估、数据获取和 QRS/CNN 共用的数据读取**。CNN 的协议、数据准备、训练、基线和依赖已迁移到顶层 [`model/`](../model/README.md)，不要在这里找 CNN 训练入口。

模型接手者先读[训练交接](../docs/model_training_handoff.md)和[model/README](../model/README.md)。

## 当前文件

| 文件 | 用途 |
| --- | --- |
| `download_mitdb_records.py` / `ecg_dataset.py` | MIT 获取、幅值读取和标注计分（QRS/CNN 共用） |
| `benchmark_qrs_v4.py` / `qrs_v4_protocol.json` | 当前 QRS 及 XQRS/GQRS 对照 |
| `benchmark_qrs_v5.py` / `qrs_v5_protocol.json` | 成熟 QRS v5 已知记录回归 |
| `benchmark_qrs_research.py` / `qrs_research_protocol.json` | 研究 26 便携复现（当前采用结果、已知开发回归） |
| `download_qrs_noise.py` / `evaluate_qrs_noise.py` / `qrs_noise_protocol.json` | 官方 NST 噪声压力评估 |
| `evaluate_qrs_auto.py` / `evaluate_qrs_peak.py` | 旧独立 QRS 候选对照 |
| `plot_qrs_benchmark.py` | QRS 波形/结果出图 |
| `analyze_capture.py` | 实际 CSV 采集输入诊断 |
| `requirements_qrs.txt` / `requirements.txt` | QRS/公共依赖 |
| `results/` | 精选 QRS 结果（含当前 `qrs_research26_20261023.json`） |

CNN 协议、`prepare_cnn_*`、`train_cnn_*`、`baseline/`、`requirements_cnn*.txt` 已移到 `model/`；旧协议字节未改，历史内部路径说明见 `model/README.md`。

## QRS 运行

从项目根目录执行，替换本机解释器路径，输出目录必须不存在：

```powershell
python -m venv tmp/qrs_env
& './tmp/qrs_env/Scripts/python.exe' -m pip install -r data/requirements_qrs.txt
& './tmp/qrs_env/Scripts/python.exe' -B data/download_mitdb_records.py --output-dir tmp/qrs_current/raw
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --stage development --output-dir tmp/qrs_current/development
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --stage evaluation --output-dir tmp/qrs_current/evaluation
```

MIT 原始文件校验官方 SHA256 及 212 首值/长度/校验和，按 MLII 选导联。QRS 采用 360Hz、4096 单位/mV 和 int16 饱和；分类采用物理 mV 及独立切拍协议，两种幅值口径不可混用。

## QRS运行时回归

`benchmark_qrs_runtime.py`按`qrs_runtime_protocol.json`分别核对360Hz原重放事件和500Hz输入转换候选。输出必须指定不存在的新目录；不依赖旧tmp，不读取分类独立测试。运行方式见[运行时说明](../docs/qrs_runtime.md)，实验结果见[运行时记录](../docs/records/runtime_20261023.md)。冻结研究快照和原门槛入口保持独立，详见[研究26](../docs/qrs_research.md)。

## 实际 CSV 输入诊断

```powershell
python -B data/analyze_capture.py --source <五列RawData.csv> --output tmp/capture_analysis_new
```

保持现有检测器参数，核对 CH2/shift8、独立滑动差分能量、因果带通/50Hz 陷波和阈值；保存完整启动/尾部，不用无标注 CSV 声称检出率。

## 旧协议

`data/protocols/` 只保留迁移说明；协议为兼容脚本默认路径已回到 `data/` 根目录。历史 CNN 协议内部字段中的 `data/cnn_mf_v1_protocol.json` 字样属于冻结旧字节，未改写；当前实际位置是 `model/protocols/cnn_mf_v1_protocol.json`。

## 分类软件闭环

`replay_classification.py`只读已有已知MIT记录，按冻结360Hz运行时自动检测/切拍，使用本地冻结的未合格开发权重核验接口，输出ECG-UART-1记录和请求/结果JSONL，不发送串口或训练。需要已有QRS环境和PyTorch环境，允许分开，不自动安装：

```powershell
python -B data/replay_classification.py --raw-dir <MIT原始数据目录> --record 100 --seconds 30 --output-dir tmp/class_replay_new --inference-python <已有PyTorch解释器>
```

输出目录必须不存在。完整输入、来源/许可和有效性合同见[分类接口](../docs/classification_protocol.md)及[模型交接](../docs/model_training_handoff.md)。原始标注不用于补峰或生成窗口；本入口不评分、不访问独立6人，不能据此报告分类准确率或板上成功。

## C移植对照与标准回放数据

verify_ps_runtime.py以原冻结360Hz全记录输出核对C主机程序的确认时刻/位置/RR，不恢复调参，不访问独立分类患者；必须显式raw/golden/executable/output。export_runtime_samples.py生成严格360Hz/4096单位的标准CSV用于新ARM回放入口，不处理厂商500Hz文件。说明和边界见[ARM运行](../docs/runtime_board.md)。
