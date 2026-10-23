# 模型训练与 CNN 资产

本目录集中存放 CNN/模型相关的协议、数据准备、训练、基线和依赖；QRS 与共用数据读取仍在 `data/`。

## 结构

```text
model/
├── README.md
├── protocols/              # 8 个 cnn_*_protocol.json（旧字节未改）
├── prepare/                # 数据准备、下载、切拍、分类盘点
│   ├── prepare_cnn_cv.py
│   ├── prepare_cnn_expanded.py
│   ├── prepare_cnn_git.py
│   ├── extend_cnn_ltdb.py
│   ├── download_external_ecg.py
│   └── profile_classification.py
├── train/                  # 训练/评估入口
│   ├── train_cnn_candidates.py
│   ├── train_cnn_cv.py
│   └── train_cnn_refined.py
├── baseline/               # residual_verified 三折权重、指标、冻结协议
├── requirements_cnn.txt
└── requirements_cnn_data.txt
```

## 与旧路径的关系

旧入口与当前入口的对应关系：

| 旧路径 | 新路径 |
| --- | --- |
| `data/cnn_*.json` | `model/protocols/cnn_*.json` |
| `data/prepare_cnn_*.py` / `extend_cnn_ltdb.py` / `download_external_ecg.py` / `profile_classification.py` | `model/prepare/` |
| `data/train_cnn_*.py` | `model/train/` |
| `data/baseline/` | `model/baseline/` |
| `data/requirements_cnn*.txt` | `model/requirements_cnn*.txt` |

- 旧协议文件**逐字节未改**；个别历史协议内部仍写有 `data/cnn_mf_v1_protocol.json`，这是冻结时的来源标识，不作为当前路径。
- `baseline/legacy_sources/`中的同名脚本仅供冻结来源哈希核验，不是另一套训练入口；实际运行使用`prepare/`、`train/`。
- 脚本已改为从项目根定位：`ROOT=...parents[2]`；共用 `ecg_dataset.py` 仍从 `data/` 导入。
- `sim/checkout_files.json`、`sim/check_baseline.py`、`sim/check_checkout.py`、`sim/check_training_checkout.py` 与 docs/report 引用已同步到 `model/`。

## 使用边界

- 旧实验记录和失败保留在 `docs/records/`；不要按旧版本号批量启动实验。
- 运行训练前先核对[训练交接](../docs/model_training_handoff.md)、协议、数据缓存和依赖；不覆盖已评估协议，不把已查看开发数据称新测试。

## 依赖与入口检查

数据准备需要`requirements_cnn_data.txt`列出的WFDB、NumPy、SciPy等；训练需要`requirements_cnn.txt`中的PyTorch等。环境应分别核对，不能因训练入口能导入Torch就认定数据准备依赖齐全。本机两个隔离环境的区别与实际检查见[迁移记录](../docs/records/model_structure_20261023.md)。不默认安装依赖。

```powershell
python -B model/prepare/prepare_cnn_git.py --help
python -B model/train/train_cnn_cv.py --help
python -B sim/check_training_checkout.py
python -B sim/check_baseline.py
```

脚本按自身位置寻找工程根，可从其他工作目录使用绝对入口路径。`--help`仅验证入口导入/参数，不能代替数据重建、权重重放或训练。网络结构定义仍在`src/reference/ecg_*cnn.py`；本目录集中的是训练资产，并非所有CNN源码。
