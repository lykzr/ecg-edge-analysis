# CNN 资产迁移到 model/（2026-10-23）

## 目标

按用户要求把 CNN 从 `data/` 分出，归入顶层 `model/`；`data/` 只保留 QRS 资产和 QRS/CNN 共用数据读取。

## 迁移内容

| 旧位置 | 新位置 |
| --- | --- |
| `data/cnn_*.json`（8 个协议） | `model/protocols/` |
| `data/prepare_cnn_*.py`、`extend_cnn_ltdb.py`、`download_external_ecg.py`、`profile_classification.py` | `model/prepare/` |
| `data/train_cnn_*.py` | `model/train/` |
| `data/baseline/` | `model/baseline/` |
| `data/requirements_cnn*.txt` | `model/` |

旧协议文件逐字节未改；只移动位置。`data/` 保留：

- QRS：`qrs_*_protocol.json`、`benchmark_qrs_*.py`、`download_qrs_noise.py`、`evaluate_qrs_*.py`、`plot_qrs_benchmark.py`、`results/`
- 共用：`ecg_dataset.py`、`download_mitdb_records.py`、`requirements_qrs.txt`
- 采集诊断：`analyze_capture.py`
- 本目录 README 与 `protocols/README.md`

## 代码和文档调整

- 迁移后的脚本 `ROOT` 改为 `parents[2]`；共用 `ecg_dataset.py` 仍从 `data/` 导入；数据准备/训练脚本增加 `model/prepare`、`model/train` 的 `sys.path`。
- 脚本内协议/基线默认路径、`source_snapshot`、`source_sha256` 中的 `data/...` 已改为 `model/...`。
- `sim/checkout_files.json`、`sim/check_baseline.py`、`sim/check_checkout.py`、`sim/test_checkout.py`、`sim/check_training_checkout.py`、`sim/test_cnn_*.py`、`sim/test_ecg_torch.py` 已同步。
- `docs/`、`report/` 中 CNN 路径已改为 `model/...`；历史备份中对 `tmp/history/training_handoff_20261017/data/...` 的引用保持原位置，不随迁移改。
- `docs/README.md`、`data/README.md` 和新增 `model/README.md` 已更新导航/说明。

## 基线兼容

`model/baseline/manifest_start.json` 记录的是迁移前脚本哈希，不能改写冻结基线。为保持校验真实，原字节脚本保存在 `model/baseline/legacy_sources/`；`check_baseline.py` 对旧 `data/train_cnn_*.py` 记录改用该快照核对，当前训练入口由 `check_training_checkout.py` 单独核验。

## 验证

- `python -B sim/check_checkout.py`：passed（227 项）
- `python -B sim/check_baseline.py`：passed（29 文件）
- `python -B sim/check_baseline.py --metrics`：passed（pooled macro-F1 0.6239，基线未接受）
- `python -B sim/check_training_checkout.py`：passed
- `python -B sim/test_checkout.py`：4 tests OK
- CNN 单元测试：`test_cnn_git.py` 3 OK、`test_cnn_expanded.py` 6 OK、`test_cnn_ltdb.py` 3 OK
- 迁移后脚本 `py_compile`：0 失败
- `docs/`、`report/`、`data/`、根 README 本地链接：0 缺失

## 边界

- 未恢复 CNN 训练、未读取独立 6 人测试、未改 QRS 算法/协议/门槛。
- 旧 CNN 协议内部 `source_data_protocol: data/cnn_mf_v1_protocol.json` 属于冻结旧字节，未改写；当前实际位置为 `model/protocols/`。
- 未操作板卡、未写 Flash、未提交 Git。

## 后续核查更正（2026-10-23）

迁移后的训练入口和数据准备入口需要各自的依赖环境，不能把Torch环境缺WFDB/SciPy说成代码路径失败。6个准备入口在现有QRS环境、3个训练入口在Torch环境从其他工作目录检查成功，未安装或训练。旧Windows基线清单的分隔符也已由check_baseline复用安全解析器处理，29份冻结文件不变，未在Linux原生复跑。迁移对历史bridge板上记录的路径替换导致发布证据哈希失配，已恢复原记录字节；当前model路径由本说明维护，不批量改写旧验收记录。详见[运行时与发布收尾](runtime_20261023.md)。
