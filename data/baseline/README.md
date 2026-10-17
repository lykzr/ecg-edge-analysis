# 开发对照基线

保存已选residual_verified的三折权重、归一化、验证预测/指标、训练过程和冻结协议，用于比较新方案及重放旧结果。它是未合格的开发基线，不是最终模型或新的独立测试；不放原始ECG波形、环境或数据缓存。原始INCART/MIT来源和引用见[第三方说明](../../third_party.md)，派生预测里的标签/记录/患者元数据沿用数据归属，不改标为项目自有原始数据。

```powershell
# 仅标准库：核对文件、冻结源码、协议和未开封测试状态。
python -B sim/check_baseline.py
# NumPy环境：从保存的验证预测重新计分。
python -B sim/check_baseline.py --metrics
# 在Git数据入口重建缓存后，用Torch环境重放三折权重；不训练。
python -B sim/check_baseline.py --cache-dir tmp/cnn_git/cache --replay-weights
```

缓存重建见[训练交接](../../docs/model_training_handoff.md)。files.json保存复制来源、逐文件字节与SHA256；原protocol/decision/manifest和预测原字节保留，原smoke未上板字段是当时状态。只保留已选候选，其他历史方案仍留本机tmp，并非全部历史试验都已随Git共享。复核程序要求匹配源码哈希，不能为兼容新算法重写旧结果哈希。
