# 轻量CNN的患者分组验证与来源对比

本入口承接[扩库训练](cnn_expanded.md)，用于检查模型能否推广到不同患者，以及辅助数据的作用。CNN仍是在电脑端训练/推理的四类心拍分类器，输入由专家标注位置切出的波形和历史RR；不代表自动QRS切拍、INT8或FPGA推理已验证。

## 冻结数据角色

[v8协议](../data/cnn_patient_cv_v8_protocol.json)只使用INCART中26名已知开发患者，按患者分成9/9/8人三折。三折验证是轮流用其中一组患者验证、其余两组训练，同人的全部记录始终跟随同一组。原先6名独立测试患者完全排除，脚本没有读取其测试NPZ的入口。

分组按固定种子、标注类别数量及S/F患者覆盖形成，不能按模型分数调整患者名单。验证保留自然构成、不按类别截断；训练上限在每一折内部应用。201/202等同人映射沿用父协议。原验证患者现已进入开发交叉验证，不能再称原验证成绩为未触碰评估。

折外预测（OOF）指每拍由未用该患者训练的那一折模型产生的预测；合并后覆盖全部开发患者。每折仍用本折验证分数选择停止轮次，模型方案也按这些开发分数选型，因此本轮不是全新独立测试，存在选型乐观偏差，不代替后续保留测试。

## 候选与相同条件

| 候选 | 波形网络 | 辅助来源 |
| --- | --- | --- |
| residual_verified | 既有轻量残差Conv1D | 已知MIT开发记录及当前折INCART训练患者 |
| residual_all | 同上 | 再加SVDB及LTDB未知身份辅助训练 |
| temporal_verified | 两层局部Conv1D，保留16个时间段位置 | 已知MIT开发记录及当前折INCART训练患者 |
| temporal_all | 同上 | 再加SVDB及LTDB未知身份辅助训练 |

比较来源时模型结构相同，比较结构时来源相同。未知身份辅助记录不能算成新增可确认患者；LTDB仍是未标定ADC形态归一化，导联和标定差异未消除。移除/加入来源是训练方案对比，不删除困难验证拍。

TemporalCnn为本项目自有小网络：原波形与一阶差分两通道，Conv1D(7)、Conv1D(5)，各16通道、ReLU及2倍最大池化，之后固定16段均值池化；RR(3→16)分支，拼接后全连接32→4。保留位置是待验证设计假设，不继承公开论文成绩，也没有加载预训练权重。残差方案的公开结构来源和改编边界仍见[第三方清单](../third_party.md)。

输入沿用128点/144Hz公共网格、约356ms前窗/533ms后窗，物理mV每拍标准差下限0.05；LTDB下限1ADC的例外保持父协议。仅历史RR、每折训练单独拟合标准化。两种模型统一使用自然顺序打乱、平方根类别加权交叉熵、既有训练增强、AdamW及余弦学习率；最少25轮、最多50轮、耐心10轮，完整参数和种子以冻结协议为准。

按三折macro-F1平均值选方案，相等时比较平均验证交叉熵。合并OOF和每一折都执行原工程门槛；数值是助手此前提出的工程目标，不是比赛或临床标准。未通过时保留失败和独立测试，不把某一折模型冒充全开发数据训练的最终权重。

## 复现

已有协议时直接prepare，不重新freeze；父缓存必须与协议钉住的清单及train.npz哈希相同，拒绝覆盖输出目录：

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B data/prepare_cnn_cv.py prepare --raw-dir tmp/ecg_expansion_20261017/raw --parent-cache tmp/cnn_expanded_cache_v7_20261017_01 --protocol data/cnn_patient_cv_v8_protocol.json --output-dir tmp/cnn_cv_cache_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B data/train_cnn_cv.py --cache-dir tmp/cnn_cv_cache_new --protocol data/cnn_patient_cv_v8_protocol.json --output-dir tmp/cnn_patient_cv_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B sim/verify_cnn_cv.py --cache-dir tmp/cnn_cv_cache_new --run-dir tmp/cnn_patient_cv_new --output tmp/cnn_cv_verify_new.json --replay-weights
```

环境路径为本机示例，其他环境使用实际解释器；不自动安装依赖。准备阶段仅复用父TRAIN中的非INCART部分，26名开发患者重新生成自然构成缓存，不加载父TEST。新设计才运行freeze，不能覆盖已评估的协议。

每折保存权重、训练/验证数量、患者身份、RR统计、epoch日志及预测；每方案保存OOF混淆矩阵和逐患者指标；最终decision只选择开发方案，不自动训练全量最终模型、开封独立测试、量化或发布。运行源码快照、数据和权重哈希必须与结果同时保留。

检查器独立复算混淆矩阵、逐类/逐患者指标、采样和标准化、方案选择及门槛，`--replay-weights`重放全部验证拍核对预测。输出仍属派生产物，文字分析与失败过程见[本轮记录](records/cnn_patient_cv_20261017.md)。**smoke仍未上板测试。**

后续同折权重微调及仅训练数据的类别比例校正另见[v9工程入口](cnn_target_adapt.md)，原v8协议及结果保持原样。

当前交接入口、可直接复制的开发缓存和权重清单见[训练交接](model_training_handoff.md)。历史v9及v10/v11专用代码已归档，不作为默认训练路线。
