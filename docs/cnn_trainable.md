# 可训练轻量CNN的运行与评估

> 历史方案说明：专用脚本/协议已归档，下面的旧命令不能直接执行。归档与恢复规则见[训练交接](model_training_handoff.md)，当前入口采用患者CV流程。

本入口承接[固定模板基线](cnn_baseline.md)。卷积层在训练中自动学习，训练仍在电脑端；这里不等于模型已经能在FPGA运行。CLEF预训练方案继续保留备选，不在本轮恢复。

扩大数据范围及新患者隔离验证/测试使用[扩库训练入口](cnn_expanded.md)。下文各原协议保留其原始划分，不与扩库版本混写。

## 来源与实现边界

- MF-CNN参考[Farag 2023](https://doi.org/10.3390/s23031365)的单Conv1D、BatchNorm、tanh、全局最大池化、共享RR分支。采用可训练卷积，随机初始化，12个滤波器；输入保留64点及三个因果RR，不使用论文后RR特征。
- 小型残差CNN参考[Kachuee等2018](https://arxiv.org/abs/1805.00794)的双Conv1D/跳连/池化心拍结构思路，缩成3块、16或32通道，并增加因果RR分支及BatchNorm；不是其5块原网络、原预处理或论文成绩复现。
- 全部代码独立实现，不复制作者代码、权重、图表或长段论文。参考论文的许可分别保留，不能因架构借鉴就把外部资料改标MIT。
- 修改版比较训练集RR标准化、自然分布加权损失、去BatchNorm及小幅时间/幅值/噪声增强；所有拟合、采样和增强限训练集。去BatchNorm是结构变体，不能将不同变体的资源和准确率拼接。

## 数据与冻结协议

协议为[可训练初轮](../tmp/history/training_handoff_20261017/data/cnn_trainable_v2_protocol.json)、[针对训练/验证诊断的改进轮](../tmp/history/training_handoff_20261017/data/cnn_refined_v3_protocol.json)、[长上下文轮](../tmp/history/training_handoff_20261017/data/cnn_context_v4_protocol.json)和[双通道MF改进轮](../tmp/history/training_handoff_20261017/data/cnn_mf_refined_v5_protocol.json)。类别、导联、切拍和16/4/22受试者集合保持首轮协议，缓存来自`tmp/cnn_mf_v1_20261017_01/`并逐文件核对哈希。脚本不把某拍改为其它集合，也不删除困难类别或按结果删记录。

长上下文轮保留同一受试者角色，窗口扩为`[R-128,R+192)`，320个360Hz点重采样为128个144Hz点，需等待R后约533ms波形；没有后RR标注输入。仅因外层窗口不完整额外排除边界心拍并记录，不能拿不同输入长度的MAC或样本数量当完全相同实验。

固定模板首轮已经看过旧测试结果；各冻结轮次只在训练/验证选型完成并保存选择后，才读取旧测试缓存进行一次回放；最终候选仍只按验证结果比较，不按这些回放分数挑选。这是已查看数据上的探索性对照，不是新的独立测试。验证F只有11拍，不能据较高验证分数夸大可靠性。

本轮先固定工程目标：macro-F1至少0.85、各类F1至少0.70、N/S/V/F召回分别至少0.95/0.80/0.80/0.70，参数不超过100000。此目标是助手在本轮训练前提出的原型筛选条件，不是用户指定、竞赛硬要求或临床标准；不因结果差而降低。最终泛化、INT8损失和硬件验收另行验证。

## 环境与运行

用户已明确允许安装CPU PyTorch及必要依赖到项目独立环境。当前可用解释器为`tmp/cnn_torch_env/Scripts/python.exe`；其它机器使用自己的独立环境。安装位置、临时文件、下载缓存均放tmp，不改系统Python或驱动。依赖见[model/requirements_cnn.txt](../model/requirements_cnn.txt)，实际完整环境清单留实验输出旁；本入口不自行执行安装。

从项目根目录，分别使用新的输出目录：

```powershell
& './tmp/cnn_torch_env/Scripts/python.exe' -B -m unittest discover -s sim -p 'test_ecg_torch.py'
& './tmp/cnn_torch_env/Scripts/python.exe' -B model/train/train_cnn_candidates.py --cache-dir tmp/cnn_mf_v1_20261017_01 --output-dir tmp/cnn_trainable_v2_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B model/train/train_cnn_refined.py --cache-dir tmp/cnn_mf_v1_20261017_01 --output-dir tmp/cnn_refined_v3_new
```

长上下文先在已有WFDB/SciPy环境运行`model/prepare/prepare_cnn_context.py --original-cache <旧缓存> --raw-dir <原始记录> --output-dir <新缓存>`，再给`train_cnn_refined.py`传入`--protocol model/protocols/cnn_context_v4_protocol.json`和新缓存。v3冻结协议继承的`training.augmentation`说明仍提到initial suite；实际是否增强以每个候选的`augment`及冻结源码为准，本轮记录保留此元数据瑕疵，不事后改写已跑协议。

输出有协议/源码快照及哈希、逐候选权重/逐轮记录、选择依据、所选模型的逐类/逐记录结果与预测。v3/v4/v5的RR归一化参数另存normalization.json，推理必须匹配；v2不使用该参数。模型权重仅加载本机本轮产生的state_dict，采用weights_only方式，不加载不明pickle。

CPU固定线程数与随机种子，调用确定性算法；跨PyTorch版本/平台不承诺字节级相同。Conv/Linear MAC只作为算术预算，不含预处理/激活/传输等，不是板上延迟、功耗或综合资源。实际结果和失败分析见本轮训练记录。**smoke未上板测试。**
