# QRS逐样本运行时与切拍

> 当前状态：360Hz阶段基线和旧失败保留；2026-10-24用户已明确恢复500Hz衔接，独立C适配路径达到已知记录配对等效，详见[500Hz说明](rate500.md)。旧InputRuntime(500)的61抽头方案仍未采用，不把它当新路径。风险与恢复条件见[主体计划](../report/system.md#qrs暂停决定与风险)。

## 用途与边界

`src/reference/ecg_qrs_runtime.py`把研究26的两个源检测器和截止确认逻辑组合成逐样本软件参考。冻结的`qrs_research/`源码、门槛和旧成绩保持原样；本入口不替换现有PS/RTL或已验发布镜像。

研究26仍是已知42条中41条通过，105未过。这里核验运行方式和输入接口，不借目录整理或运行时转换宣布算法合格。官方噪声压力实验的失败也继续有效。

## 数据与时序合同

- `ResearchRuntime.push`只接收360Hz、4096单位/mV的int16；样本号从0开始。可选`sequence`必须连续，缺口/重复报错后应结束会话并显式重置，不能跨缺口计算RR。
- 两个检测源随样本同步推进；主候选再等待72个内部样本，与原重放的200ms截止一致。事件为`(emitted, position, rr)`；`emitted`是实际确认时刻，`position`才是波形标记位置。首事件`rr=0`表示未知。
- 原波形环形缓冲4096点，待确认队列32项、辅助事件缓存32项、最多8个模板。关闭只追加不读取的audit历史；不保留全输入或全部输出。调用方应及时消费结果。Python浮点状态和计数器不是整数硬件资源预算。
- `finish()`不填补未来样本、不冲出未到截止的候选；返回尾部待确认数量。启动、结束及失败记录不能从评估中删除。
- `AdcScale(baseline, counts_per_mv)`用于明确整数ADC/mV增益的输入，对称四舍五入后饱和到int16，并计数。它不是按记录调节增益的自动归一化，也不直接接受厂商34字节帧。ADS1292R标称换算与真实标定仍须按采集合同单独核对，不能把本次公开数据转换当作实采验证。

## 500Hz候选

本转换路线未通过完整逐记录门槛，暂不采用为部署输入路线；保留用于复现和诊断。具体失败见[本轮记录](records/runtime_20261023.md#500hz最终结果与采用决定)。

`InputRuntime(500)`先使用61抽头、90Hz低通FIR，再以整数时基线性重采样到360Hz，沿用冻结检测器。事件位置回到500Hz源样本号，仅扣除FIR固定30个源样本群延迟；实际确认时刻不减去等待。此路线避免直接把360Hz常数套到500Hz，但会改变输入频响，必须另计分，不继承360Hz等价成绩。

500Hz实验输入来自已知360Hz记录的离线重采样，不是新患者、原生500Hz采集或真实AFE输入。边界、削顶、误检/漏检、V召回、位置/RR及确认等待应一起报告；位置误差不能冒充计算耗时。

## 自动切拍与模型接口

`ecg_signal_pipeline.SignalPipeline`按相同源序号连接输入换算、检测和`ecg_beat_window.BeatCutter`；仅用于离线参考，不在PC显示程序中偷加检测。

切拍窗口沿用`model/protocols/cnn_git_v1_protocol.json`：峰前128/360秒、峰后192/360秒，按源采样率向上取整，左闭右开。先存源波形；检测延迟大于窗口等待时直接从历史环形缓冲取回，不能把收到事件的时刻当峰位置。

启动左侧不足的窗口明确跳过，右侧不足则等待；结束不补零，报告尾部窗口数。迟到至被覆盖或队列溢出明确报错。`BeatWindow.model_input()`复用训练端`common_window`得到128点波形，按4096单位/mV恢复mV，再做原训练窗口归一化；RR特征只使用当前和此前RR，首拍返回`None`。没有专家标注补峰，没有执行CNN推理，实际自动切拍后的分类效果仍待评估。

```python
from ecg_signal_pipeline import SignalPipeline

pipeline = SignalPipeline(sampling_hz=500)
for sequence, value in enumerate(source_int16_samples):
    events, beats = pipeline.push(value, sequence=sequence)
    for beat in beats:
        waveform, rr_features = beat.model_input()
        # waveform为128点；rr_features为None时不伪造可用分类输入。
summary = pipeline.finish()
```

厂商34字节、电脑送样ECG-IN-1、板端结果ECG-UART-1保持分开。本接口消费解码后的整数，不改这三段格式，也不把软件参考事件冒充板端返回。

## 复现

使用已具备`data/requirements_qrs.txt`依赖的解释器，从项目根运行：

```powershell
python -B -m unittest discover -s sim -p test_qrs_runtime.py
python -B -m unittest discover -s sim -p test_beat_window.py
python -B data/benchmark_qrs_runtime.py --raw-dir <mit_raw_dir> --output-dir <new_360_dir> --rate 360 --reference-run <research26_rerun_dir>
python -B data/benchmark_qrs_runtime.py --raw-dir <mit_raw_dir> --output-dir <new_500_dir> --rate 500
```

原重放目录可用[研究26说明](qrs_research.md)的两个stage命令生成；`--reference-run`仅用于逐事件比对，省略时仍可独立计分，不依赖已有tmp。输出目录存在即停止，不覆盖旧实验。冻结依据见`data/qrs_runtime_protocol.json`；实际结果与未完成项见[本轮记录](records/runtime_20261023.md)。

后续先核对分类接口、单位/编号/窗口和PS/PL分工，再做端到端软件参考及同源移植准备。QRS调参和500Hz算法路线改进已暂停；500Hz实采衔接、整数实现和新镜像/实板仍未验收，不因暂停而标为通过。

## ARM C移植入口

冻结360Hz数学流程的C实现和运行方式见[板端运行](runtime_board.md)，正式源码src/ps/ecg_runtime，实际对照/实板范围见[记录](records/system_port_20261024.md)。原Python参考、原门槛和105失败不改；C语言移植不等于模型训练、算法改善、500Hz合格或PL核心实现。
