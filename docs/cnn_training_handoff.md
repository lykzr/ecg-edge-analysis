# 四分类CNN训练接手说明

本分支 `training/cnn-fourclass-h27` 用于另一位队员接续训练。起点为 `merge` 的 `5fa3f3e64b575b492a1d859a2e207c6b1c8d555b`；新模型只增加在 `model/cnn_fourclass/`，没有把它接成网页或固件默认模型。`main`、`merge` 和原 `feature/ecg-model` 分支不因本交接改变。

## 当前模型和成绩

H27：单次残差1D CNN，128点当前心拍双通道（原波及差分），加原RR分支、归一化RR3、122项因果形态/已完成历史背景特征、最近8个历史RR，共269维，分类头64隐藏单元输出N/S/V/F。25,476参数，619,608 Conv/Linear MAC/拍；这不是综合、时序或板上加速结果。HGB只在训练期提供三类软目标，学生V/F只在蒸馏损失中合并，四类真标签始终用于分类损失；推理不运行HGB、不等待下一拍。

|类别|精确率|召回率|F1|
|---|---:|---:|---:|
|N|99.04%|98.46%|98.75%|
|S|50.36%|83.69%|62.88%|
|V|92.65%|93.91%|93.27%|
|F|30.00%|16.77%|21.51%|

N/S/V平均F1 84.97%，四类宏F1 69.10%，总体准确率97.70%。主要瓶颈S误报，**未达到N/S/V各率95%**。N含部分传导/逸搏类型，不表示健康；F为融合心拍。证据见[原始聚合结果及资源](evidence/cnn_fourclass_handoff_20261102.json)和[便携重放检查](evidence/cnn_fourclass_portable_check_20261102.json)。

这些是26位INCART开发患者、三折患者隔离、143916参考拍/61份历史C自动检测切拍缓存的开发成绩，全部漏检/额外检出计入。MIT-BIH允许辅助样本30842拍只参加训练。201/202归同一患者；INCART保留患者8/10/22/23/31/32继续封存。多次开发选择有乐观偏差，不能称新独立测试或临床成绩。患者与fold表、类别符号、采样上限及种子见[固定协议](../model/cnn_fourclass/protocol.json)。

三个文件 `assets/fold_0.pt`、`fold_1.pt`、`fold_2.pt` 是对应留出折的完整便携状态字典（包含卷积/RR/头权重及该折RR归一化），不是三个独立病种模型，不默认投票或按分数选最好折。未来全开发数据最终拟合及独立测试需要另行冻结程序。文件SHA和原头权重身份见[资产清单](../model/cnn_fourclass/files.json)、[来源记录](../model/cnn_fourclass/provenance.json)。

## 克隆与环境

```powershell
git clone --branch training/cnn-fourclass-h27 --single-branch https://github.com/lykzr/ecg-edge-analysis.git
cd ecg-edge-analysis
python -m venv .venv-training
.venv-training\Scripts\python.exe -m pip install -r model/cnn_fourclass/requirements.txt
.venv-training\Scripts\python.exe -X utf8 model/cnn_fourclass/check.py
```

使用Python 3.11或3.12。以上安装命令由接手者在自己的专用环境按需执行，本次交接未安装软件。也可用已有兼容环境；CPU PyTorch2.3.1与NumPy2会有二进制桥警告，本入口采用frombuffer/列表传值，本机检查已通过。GPU或其他版本需重新数值核验。合成自检36向量不读取心电数据，不训练。

## 数据准备（0拟合）

不上传原始ECG或整个本机tmp。仓库已有公开数据下载/基础输入重建入口，仅获取固定允许记录：

```powershell
python -X utf8 model/prepare/prepare_cnn_git.py download --raw-dir tmp/cnn_raw
python -X utf8 model/prepare/prepare_cnn_git.py prepare --raw-dir tmp/cnn_raw --output-dir tmp/cnn_base
python -X utf8 model/inference/build_native.py --cc C:/path/to/gcc.exe
python -X utf8 model/cnn_fourclass/prepare.py rebuild --raw-dir tmp/cnn_raw --base-cache tmp/cnn_base --output tmp/h27_dataset
```

`build_native.py`只构建已有模型侧电脑检测/重切拍C程序，不写板卡；Linux可指定已有 `gcc`。没有编译器时先由接手者准备工具。原始记录按官方SHA校验，基础输入逐数组复现，历史背景必须来自全部已完成窗口，在辅助抽样前生成；历史RR来自全部已知心拍时序，不是只用抽样后相邻行。自动输入重新执行现有C检测/重切拍，采用原固定50ms匹配。最终字段与[预期摘要](../model/cnn_fourclass/expected_inputs.json)严格比较；失败应查依赖、输入和算法差异，不改预期绕过检查。

如接手者持有本机已有完整原缓存，可选快捷导入（这不是运行必需路径）：

```powershell
python -X utf8 model/cnn_fourclass/prepare.py import-cache --original-root D:/path/to/original-checkout --output tmp/h27_dataset
```

`--smoke-record incartdb:I01`只生成部分记录调试缓存，标记complete=false，训练入口拒绝它。重建输出目录必须不存在，不覆盖旧结果。数据缓存只能本地保留；协议中六名封存患者没有下载/读取入口。

## 接续训练

先运行完整重放与0拟合预检：

```powershell
python -X utf8 model/cnn_fourclass/check.py --dataset tmp/h27_dataset --output tmp/h27_replay.json
python -X utf8 model/cnn_fourclass/train.py --dataset tmp/h27_dataset --output tmp/h27_preflight
```

续训需明确获得当前训练授权，再显式加 `--train`：

```powershell
python -X utf8 model/cnn_fourclass/train.py --dataset tmp/h27_dataset --output tmp/h27_continue_01 --train --epochs 40 --fold-seconds 180 --batch-seconds 600
python -X utf8 model/cnn_fourclass/check.py --dataset tmp/h27_dataset --run tmp/h27_continue_01 --output tmp/h27_continue_01/verification.json
```

这会**从已保存H27继续训练分类头**，不是复跑H27从H26起点的历史优化轨迹；代码与协议都明确这一区别。本次交接没有执行 `--train`。默认4线程、三折、每折最多40轮/180秒、总600秒，至少20轮后连续12轮无改善早停，保留epoch0。达到预算停止，不自动续跑或搜索其他参数。本交接参考入口使用focal gamma2且不使用教师KL（与历史H27不同），原拍质量守恒，配对专家/自动各半，F训练权重乘0.2；按完整自动链N/S/V平均F1选检查点，四类及患者都报告。

本交接不上传旧教师软目标缓存；推理和新的参考训练均不依赖它们。H27历史训练用过教师蒸馏的事实保留在来源及历史摘要。队友可在H27基础上改变卷积训练范围、损失、采样或其他方法；这个有限参考入口不强制延续我的方案。改变方法时重新固定实验协议、保留患者隔离和完整四类计分，避免把验证集合变化误当模型提升。

训练后必须执行上述 `check.py --run`，从保存权重重新逐拍推理并独立向量计数。不要仅比较一次训练日志的汇总，也不要用一个高总体准确率判定所有类都合格。新实验保留独立目录、协议、随机种子、输入/源/权重SHA、完整失败记录。

## 推理接口和系统边界

```python
from model.cnn_fourclass.network import classify_mv
result = classify_mv(samples_mv, fold=0, preprocess="hp05", sampling_hz=500)
# result["prediction"] 为N/S/V/F索引0/1/2/3；无效为-1。
```

这是**整段连续记录电脑参考**，每次调用重建状态，不能把实时小块逐次独立调用。首选500Hz CH2原始ADC正确换算的mV→hp05；若确为匹配的因果0.5Hz高通输出才用raw。其他带通、陷波或网页零相位显示列未纳入此模型合同。模型4096 codes/mV是内部量化标度，不是ADS原始ADC转换系数。当前入口复用已有检测/切拍代码，H27忽略其HGB输出/后继特征，以ready500为决定时刻；连续跨块/断流重置需系统侧另验。

H27尚未完成专属INT8校准、PL整网、实板分类及同条件ARM/FPGA性能比较。H16/H18的旧整数成果不能替代H27新结构验证。正式网页/固件/Flash/latest均未切换。后续建议先固定输入和候选，再做H27专属量化与逐层核对，保留11月4日18:00北京交付期限及联调/报告时间；不要继续无限头宽/损失网格搜索。

## 避免重复实验

[H1—H27历史方法与真实指标](../model/cnn_fourclass/history.json)保留失败和无收益结果。H9用额外编码计算，H16为单次CNN基线，H22增加训练期HGB蒸馏，H23/H24开放卷积未带来实质收益，H25引入历史RR8，H26扩大头至64，H27 focal只在一折超过起点。不同候选的时序及整数验证阶段不同，不能只排总体准确率。建议接手者先确认S类误报的患者分布及采集输入差异，再冻结单项假设，不直接无限续训。

## H27训练交接派生资料

旧H27训练曾使用本项目v92 HGB的训练期概率软目标；这些缓存仅保留本地，不随本次交接上传。公开数据使用沿用仓库根third_party.md的INCART和MIT-BIH来源、引用及使用边界。CNN完整状态字典为本项目训练结果；结构复用仓库自有实现，依赖PyTorch/NumPy/SciPy/WFDB，依赖各自许可仍适用。原始ECG及商家资料没有随本交接上传。

合成自检输入可用 `python model/cnn_fourclass/generate_synthetic.py` 逐值核验来源：固定种子2026110200/1/2生成36组随机/零值/常量输入，只读取完整模型权重及合成对照，不读取患者记录或训练缓存。
