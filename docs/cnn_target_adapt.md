# 目标来源微调与类别比例校正

> 历史方案说明：专用脚本/协议已归档，下面的旧命令不能直接执行。归档与恢复规则见[训练交接](model_training_handoff.md)，当前入口采用患者CV流程。

本入口承接[患者CV](cnn_patient_cv.md)，使用同一26名INCART开发患者、三折及128点波形/RR定义。原6名独立测试患者仍排除。本轮是已知开发数据上的受控比较，不是新独立测试，不表示真实采集、INT8或PL推理已通过。

## 实验设计

[v9协议](../tmp/history/training_handoff_20261017/data/cnn_target_adapt_v9_protocol.json)钉住v8协议、缓存、运行清单、决策以及每折父权重/标准化哈希。不改v8源码、协议和失败结果。每折只从该折residual_verified权重出发，禁止用其他折已经见过当前验证患者的权重。

| 阶段 | 训练方式 |
| --- | --- |
| base | 直接重放本折v8父权重，不继续训练 |
| natural | 仅本折INCART训练患者，普通交叉熵微调 |
| patient | 同一训练样本，加入患者/类别权重微调 |

微调只将N训练拍限制为每患者2000，其余类别全部保留；验证始终保留自然构成。RR沿用本折父模型从训练数据拟合的标准化，不用验证重拟合，也不因输入坐标变化干扰父权重。两种微调统一低学习率0.0001、AdamW、同一增强/顺序种子、12—25轮及耐心6轮；仅按原始alpha0验证macro-F1选checkpoint，相等看原始交叉熵。完整参数以冻结协议为准。

patient权重先按每个“患者、类别”的样本数取平方根倒数，在各类内部归一均值，再乘类别比例的平方根倒数；整体均值归一后截断到0.1—10。损失使用各拍交叉熵乘权重后取批均值，不按每批随机权重和再除一次。目标是减少少数几个患者主导某类，不承诺提升。

## 类别比例校正

每阶段在alpha=0、0.5、1三种预定强度下比较同一组网络输出：

```text
corrected_logits[c] = logits[c] + alpha * (log(target_prior[c]) - log(effective_train_prior[c]))
```

target_prior只由本折未截断INCART训练患者的类别计数得到，不能用验证/测试患者的数量。base的effective_train_prior按v8训练计数平方根归一得到，与其平方根类别损失权重对应；natural按实际微调计数；patient按实际各拍损失权重的逐类和归一。截断后的权重也计入该比例。

这是假设类别条件分布近似不变时的比例校正研究，不是已经证明成立的域迁移或概率校准。微调未必完全达到新目标的最优分布，也可能有形态和标注差异，因此必须实测精确率和召回率的取舍，不能把误报减少直接当合格。alpha为开发集候选参数，选择它会进一步消耗开发验证，不能称未调参测试。

effective_train_prior是由训练计数/损失权重推导的名义比例。父模型原来的批内加权归一、有限轮次优化和患者条件分布差异，使实际网络输出未必严格符合这个简化比例；本轮只把公式作为固定候选变换，不称已恢复真实概率。

三阶段×三种alpha共9个开发方案，各三折；其中实际重新训练的是两阶段×三折=6次。按三折平均macro-F1选方案；原始混淆矩阵、逐患者结果与每个候选的失败门槛均保留。沿用原工程验收，不降低门槛或删S/F；通过各折和合并门槛后仍需另立最终拟合/测试流程。

## 复现与检查

在项目根目录使用已有隔离环境；输出路径不能已存在：

```powershell
# 只有设计新协议时freeze；已有v9协议不能重新生成覆盖。
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B data/freeze_cnn_adapt.py --cache-dir tmp/cnn_cv_cache_20261017_01 --parent-run tmp/cnn_patient_cv_v8_20261017_02 --output data/cnn_target_adapt_new_protocol.json
& './tmp/cnn_torch_env/Scripts/python.exe' -B data/train_cnn_adapt.py --cache-dir tmp/cnn_cv_cache_20261017_01 --parent-run tmp/cnn_patient_cv_v8_20261017_02 --protocol data/cnn_target_adapt_v9_protocol.json --output-dir tmp/cnn_target_adapt_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B sim/verify_cnn_adapt.py --cache-dir tmp/cnn_cv_cache_20261017_01 --parent-run tmp/cnn_patient_cv_v8_20261017_02 --run-dir tmp/cnn_target_adapt_new --output tmp/cnn_target_adapt_verify_new.json
```

路径为本机示例，其他机器替换解释器和对应父运行目录；不能随便选择不匹配的权重。新模型在tmp保留源码快照、环境、哈希、epoch、权重、原始logits、各alpha预测、采样索引和损失权重。没有test读取入口，不自动开封、量化、部署或发布。

[独立检查器](../tmp/history/training_handoff_20261017/sim/verify_cnn_adapt.py)重新构造采样/权重/比例与模型，重放全部开发验证，独立复算逐类和逐患者指标、门槛与方案选择。来源沿用[第三方说明](../third_party.md)中的既有残差自有改编及PyTorch，不下载新预训练权重。实际实验与局限见[记录](records/cnn_target_adapt_20261017.md)。**smoke尚未上板测试。**

后续新增的标签无关历史形态背景另见[v10入口](cnn_background.md)，不改本轮协议和取舍结果。
