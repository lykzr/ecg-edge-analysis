# 轻量MF-CNN分类基线

> 历史方案说明：专用脚本/协议已归档，下面的旧命令不能直接执行。归档与恢复规则见[训练交接](model_training_handoff.md)，当前入口采用患者CV流程。

本入口用于在电脑端训练单心拍分类基线。QRS负责找出一次心跳的位置，CNN负责根据波形与RR特征分类；先用专家标注位置切拍，后续另测自动QRS切拍的端到端效果。这里不是FPGA推理或临床诊断程序。

## 来源与改编

网络复用Farag 2023论文[A Tiny Matched Filter-Based CNN](https://doi.org/10.3390/s23031365)第4节/图3的固定匹配模板卷积、全局最大池化、共享RR全连接分支和分类头思路。论文为CC BY 4.0；本库独立实现，没有复制第三方代码、模型权重或图表，不是官方预训练模型或论文成绩复现。

本页保留固定模板首版的复现入口，当前改进工作见[可训练CNN](cnn_trainable.md)；[CLEF-Small](model_candidates/clef_small.md)继续保留备选。选择固定模板变体，可使用现有NumPy/SciPy/WFDB环境先建立可复现训练入口。卷积核由训练心拍求均值得到，训练过程优化RR分支与分类头，不能说全部卷积参数都经反向传播学习。

与论文的具体区别：采用N/S/V/F四个超类模板、三个因果RR特征，不读取后一个RR；采用当前心拍归一化和仅训练集拟合的池化特征标准化，再做tanh；没有复现可训练BatchNorm。论文较好成绩、参数规模与本实现不能直接互用。tanh、重采样和浮点归一化的INT8/硬件实现仍需单独设计。

## 数据和协议

冻结配置为[data/cnn_mf_v1_protocol.json](../tmp/history/training_handoff_20261017/data/cnn_mf_v1_protocol.json)。使用当前42条MIT-BIH原始记录，MLII，按官方SHA及双通道212校验核查；分类使用物理mV，不沿用QRS的16位输入饱和。N组包含束支阻滞与逸搏，不能把N叫作健康人。

借鉴论文DS1/DS2的记录方案，但201因与测试202同一受试者而排除，207仍在现有VF范围之外；剩余DS1中固定4条作为验证，其余16条训练，DS2的22条测试。所有42条曾参与QRS研究，本轮是分类器层面的隔离评估，不是全系统未见数据验证，也不能称标准DS1/DS2原样复现。验证记录选择使用过类别支持盘点，没有看CNN结果再调划分。

窗口为`[R-90,R+90)`，360Hz的180点分段用16/45多相重采样为64点；对分段边界之外按重采样器零延拓，不补缺失的记录尾端心拍。逐拍减均值，再除以max(标准差,0.05mV)，不使用整记录统计。缺完整窗口、首拍无RR和未映射标签分别统计；不按预测正确与否删拍。

三个RR特征仅依赖当前和历史R位置；历史80/400间期均值不含当前pre-RR，启动不足时用已有历史，首个间期用自身作分母。比值裁剪0—4再除4。专家标注的过去位置仍是理想输入，不能代替实际检测器漏检/误检后的鲁棒性。完整心拍采样本身还需等待R后约250ms，这不是计算耗时。

四个卷积核仅由训练集计算，分类权重/模板/特征归一化/类别权重/早停均不接触测试结果；测试只在验证选权重完成后评价一次。预设80轮上限、12轮无改善早停，按验证macro-F1选择权重，不以总体准确率挑选。

## 运行

从项目根目录，使用已有NumPy、SciPy、WFDB环境；无需PyTorch/TensorFlow。本入口不会自动安装依赖。输出目录必须不存在，所有数据缓存、权重和完整JSON写tmp，保留日志写docs/records。

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B -m unittest discover -s sim -p 'test_ecg_cnn.py'
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B data/train_ecg_cnn.py --raw-dir tmp/multi_record_20261016_01/raw --output-dir tmp/cnn_mf_v1_new
```

其他电脑替换解释器/原始数据/新输出目录，协议路径默认根据脚本定位项目根。若本机没有同名环境，使用自己已有且具备依赖的解释器，不把本机路径当统一配置。

输出包括protocol.json、三集合NPZ、best_weights.npz、验证选权重依据、逐轮训练记录（manifest.json内）、三集合逐类/逐记录指标与预测。NPZ采用纯数值/字符串数组，不需pickle。来源/环境/数据哈希保存在manifest.json。当前结果与限制统一见[训练记录](records/cnn_mf_v1_20261017.md)，README不写成绩。
