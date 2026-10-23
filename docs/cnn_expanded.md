# 扩展数据的轻量CNN训练

后续开发验证入口见[患者CV与来源对比](cnn_patient_cv.md)。该版本将原训练/验证26名INCART患者统一视为已知开发数据，保留原6名独立测试；本文v6/v7协议和原结果保持不变。

本入口使用[冻结协议](../model/protocols/cnn_expanded_v6_protocol.json)，承接[原候选训练入口](cnn_trainable.md)。CNN是电脑端训练的心拍分类器：输入标注位置附近的波形和历史RR特征，学习N/S/V/F分类；不替代QRS检测，也不表示已实现FPGA推理。

本任务只覆盖约定四类心拍；N分组含束支传导阻滞等类型，不等于心脏健康，S不等于房颤，V不等于室速/室颤。Q/起搏及范围外输入不属于当前训练输出，未知/质量不足出口仍待设计与验证。心拍、连续节律和疾病判断的区别见范围记录。

## 数据与身份边界

- INCART 1.0.0：按官方患者编号分组，不能将同人的多个I编号记录随机分开。导联II，257Hz；专家修正类别，但标注位置没有逐拍人工校正。
- MIT-BIH 1.0.0：MLII，360Hz；原42条已查看记录在本版全部转为已知开发训练数据。旧协议、失败结果和测试记录保留，本版不能冒称复现原16/4/22划分成绩。
- SVDB 1.0.0：ECG1，128Hz。官方未提供足以确认独立患者身份的映射，不称为78名受试者。全库仅用于辅助训练，身份统一为未知来源组；ECG1导联位置不确定，不能改叫MLII或II。
- 新验证/测试只取未用于训练的INCART患者，整个患者的全部记录保持同一角色。这是混合来源训练后的INCART留人评估，训练也有INCART患者，因此不能称整个数据库均未参与训练的外部验证。相对旧MIT方案，来源、导联与采样条件发生变化；匿名数据不能证明跨数据库绝对不存在同人。

先下载头文件与标注，用患者级类别数量、固定种子和预设分层目标选择20/6/6人，保存协议后才下载波形。划分可查看类别数量，不能使用模型表现或波形外观选择“容易”的患者。独立性指对训练和选型隔离，不表示测试标签对评估者不可见。

冻结协议的`scope`使用`external-domain`描述新来源，按上述混合训练语义理解，不代表整库留出；保持原协议字节，不用事后改字掩盖原措辞不够精确。

## 输入、训练与测试

输入使用物理mV，窗口覆盖R前约356ms、后约533ms。各原采样率分别截取完整窗口，局部多相抗混叠重采样并对齐公共144Hz网格，输出128点；每拍减均值、除以至少0.05mV的标准差。不拟合标注时间偏移，不使用整段统计或后RR。零填充边界的滤波瞬态随原采样网格变化，主体对齐检查不能证明不同数据域等价。

历史RR不读取下一心拍，训练集独立拟合RR标准化。仅训练样本按协议限制每名可核实患者/每类的最大数量；SVDB使用记录为采样单位，不能因此把记录算为患者。验证/测试保留自然患病构成，只排除预定的首拍、未知标签和不完整窗口，并输出数量。每类统计与逐患者结果均保留，不能用总体准确率掩盖S/F失败。

训练候选及停止条件在协议中固定，权重与候选只按新验证macro-F1选择。`train`阶段不加载测试NPZ；选型文件落盘后，先核查所选候选的验证门槛，验证不合格时不执行`evaluate`，保存失败并保留测试集。验证合格后，`evaluate`阶段只评估所选模型一次，先写测试开封标志。开封后不能再称未触碰测试，也不能用该分数调参再报同一独立成绩。需要继续开发时另立协议，说明测试已知状态。

门槛数值沿用原候选轮次的助手工程目标，不能解读为竞赛或临床标准。冻结协议`gate.scope`继承了旧测试回放的描述；本版本实际脚本对新验证和新测试都执行这些相同数值门槛，只有两者通过才标记本轮筛选通过，仍不代表完整系统验收。

## 复现步骤

从项目根目录执行，示例环境见[依赖与CPU环境](cnn_trainable.md#环境与运行)。下面的输出路径必须是新路径；现有协议不能覆盖。

```powershell
# 已有冻结协议时不重做freeze；只恢复数据下载。
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B model/prepare/download_external_ecg.py --stage metadata --output-dir tmp/ecg_expansion_new/raw
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B model/prepare/download_external_ecg.py --stage waveforms --output-dir tmp/ecg_expansion_new/raw --protocol model/protocols/cnn_expanded_v6_protocol.json
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B model/prepare/prepare_cnn_expanded.py prepare --raw-dir tmp/ecg_expansion_new/raw --mit-raw-dir tmp/multi_record_20261016_01/raw --protocol model/protocols/cnn_expanded_v6_protocol.json --output-dir tmp/cnn_expanded_cache_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B model/train/train_cnn_expanded.py train --cache-dir tmp/cnn_expanded_cache_new --output-dir tmp/cnn_expanded_train_new
# 先检查selection_before_test.json中selected.validation.gate.passed；只有true才执行下一行。
& './tmp/cnn_torch_env/Scripts/python.exe' -B model/train/train_cnn_expanded.py evaluate --cache-dir tmp/cnn_expanded_cache_new --output-dir tmp/cnn_expanded_train_new
```

`freeze --raw-dir <元数据目录> --protocol <新协议文件>`只用于新版本设计，不覆盖已经跑过的协议。不同机器替换环境路径；脚本按自身位置定位项目，不依赖用户名。MIT原始数据可用已有下载脚本获取，不能省略所需官方SHA256清单。

波形下载使用官方归档端点的有限大小Range请求，分块放原始目录内的`.parts_*.dat/`，可恢复；最终完整文件必须与固定版本官方SHA256一致。缓存另核对所用导联的WFDB首值与校验和。输出保留协议/运行源码快照、环境、数据/权重哈希、训练采样前后计数、混淆矩阵及逐患者结果。原始波形、NPZ、权重和预测留tmp，文本日志和实验结论留docs/records。

许可及引用见[第三方清单](../third_party.md)；本工作未操作板卡、Flash或发布目录。**smoke未上板测试；本分类仍为专家位置切拍，INT8及FPGA推理另行验证。**

## 长程辅助版本

[v7协议](../model/protocols/cnn_expanded_v7_protocol.json)在v6之上增加MIT-BIH Long-Term ECG 1.0.0，仅扩展训练。v6旧结果保留，验证和测试NPZ逐字节复制；验证已经用于开发，独立测试仍须保持未用于选型。不能把这些7条长记录称为7名已确认的新患者，整库按未知身份训练组隔离。

该库ECG1的解剖导联位置未知，原始增益字段为0。WFDB读取头文件时会代填200，这不是实际标定证据。此版本明确读取数字ADC值，按每拍形态归一化，标准差下限1个ADC计数；不把它转换成人体mV，也不用于幅值、噪声电压或真实AFE结论。其它源保持v6物理mV流程。这是输入归一化后的辅助训练研究，不能声称输入导联与幅值条件完全一致。

`extend_cnn_ltdb.py`先校验父协议/数据哈希，再只对预选辅助训练拍提取波形；选择依固定哈希和每记录/每类上限，全部原标注心拍仍更新历史RR。RR历史只需最多401个间隔，避免长记录反复复制全历史；与完整历史的特征等价性有检查。所用导联核对首值/校验和，完整文件仍核对官方SHA256。

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B model/prepare/extend_cnn_ltdb.py metadata --raw-dir tmp/ecg_expansion_20261017/raw/ltdb --protocol model/protocols/cnn_expanded_v7_protocol.json
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B model/prepare/extend_cnn_ltdb.py download --raw-dir tmp/ecg_expansion_20261017/raw/ltdb --protocol model/protocols/cnn_expanded_v7_protocol.json
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B model/prepare/extend_cnn_ltdb.py prepare --raw-dir tmp/ecg_expansion_20261017/raw/ltdb --parent-cache tmp/cnn_expanded_cache_20261017_01 --protocol model/protocols/cnn_expanded_v7_protocol.json --output-dir tmp/cnn_expanded_cache_v7_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B model/train/train_cnn_expanded.py train --protocol model/protocols/cnn_expanded_v7_protocol.json --cache-dir tmp/cnn_expanded_cache_v7_new --output-dir tmp/cnn_expanded_v7_new
# 仍先检查验证门槛；未通过时保留测试，不执行evaluate。
```

`metadata`获取该版本的`RECORDS`、`SHA256SUMS.txt`与全部`.hea/.atr`元数据，`download`再获取波形。使用已有冻结协议时不能跳过校验，也不能重新生成后冒充同一版本。

注意：本页v6/v7数据准备仍为当前CV的来源依赖；旧train_cnn_expanded.py训练/测试入口已归档，以上对应旧训练命令仅作历史查阅。接手使用[训练交接](model_training_handoff.md)中的v8开发入口，禁止沿旧命令开封保留测试。
