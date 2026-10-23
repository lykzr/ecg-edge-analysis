# 因果历史形态背景CNN

> 历史方案说明：专用脚本/协议已归档，下面的旧命令不能直接执行。归档与恢复规则见[训练交接](model_training_handoff.md)，当前入口采用患者CV流程。

本入口承接[目标来源微调](cnn_target_adapt.md)，检验增加患者历史波形背景是否改善四类心拍分类。CNN仍使用专家心拍位置切拍，不代表自动QRS、真实采集、INT8或FPGA推理通过。六名独立测试患者保持排除。

## 历史背景定义

[v10协议](../tmp/history/training_handoff_20261017/data/cnn_causal_background_v10_protocol.json)保留v8的26名开发患者三折、全部验证拍、类别、128点公共网格和验收门槛。为每个目标拍补充此前最多8个已结束心拍窗口的逐点中位数，以及可用窗口数量。

窗口可用条件是 `previous_R + ceil(fs * after_seconds) <= current_R`；新窗口的完整末端不能晚于当前R。当前拍仍按原定义等待R后约533ms形成完整输入。原生窗口裁切后局部重采样，不从裁切外读取未来信号。历史状态每条记录重置，不拼接患者多条记录或跨患者延续。

所有完整标注心拍窗口都可更新背景，包括首拍及不属于N/S/V/F输出的心拍；不按“正常”标签挑模板，不用分类标签、预测类别或后续RR决定背景。专家标注事件类型仅用于区分心拍位置与非心拍注释，因此这是标签无关的分类输入研究，并非无标注/自动检测验证。

历史可能含异常拍，称为“背景”而不是正常模板。历史不足时使用实际数量，没有历史则全零并给count0；不删验证暖机拍。负位置首标注可以建立时间顺序，但不能形成越界窗口，原RR/分类样本保持不变。

## 配对方案与模型

两组从各自v8 residual_verified折权重开始，使用相同训练拍、RR统计、种子、加权损失和增强；不使用见过当前验证患者的其他折权重。

- `current_only`：只用当前波形/差分和原3个历史RR特征。
- `causal_background`：在首层增加 `(current-background, background)` 的零初始化卷积分支，在RR支路增加 `count/8` 的零初始化分支。

新支路零初始化使两组起点逐拍预测可与父模型核对。历史组增加232个可训练参数；比较的是整个历史支路方案，不能把分数差异严格归因于纯背景信息而排除参数化变化。卷积/全连接预算另统计，不包含历史缓存、逐点中位数、切拍、重采样、归一化或传输；暂未核实这些额外处理在7020上的实现与实测成本，可考虑PS预处理但尚未部署。

只复用已知MIT开发训练来源，排除SVDB/LTDB辅助；按原v8训练上限采样。历史背景在全记录全部心拍上建立后才做训练采样，避免从按标签截断的子集伪造历史。当前/背景同步时间伸缩、偏移与增益，噪声独立；count0背景在增强后仍归零。

训练按当前折开发验证macro-F1选checkpoint，初始epoch0也可保留；至少18/最多35轮、耐心8、AdamW lr0.0003，完整配置以协议和运行源码快照为准。阶段结果按三折平均macro-F1选择，平局看平均CE；原每折和合并门槛均需通过。开发验证已被多轮选型使用，不能冒称新的独立测试。

## 复现与核对

在项目根目录执行，已有协议直接prepare，不覆盖历史：

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B model/prepare/prepare_cnn_background.py prepare --parent-cache tmp/cnn_cv_cache_20261017_01 --protocol model/protocols/cnn_causal_background_v10_protocol.json --raw-dir tmp/ecg_expansion_20261017/raw --mit-raw-dir tmp/multi_record_20261016_01/raw --output-dir tmp/cnn_background_cache_new
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B sim/verify_cnn_background_data.py --cache-dir tmp/cnn_background_cache_new --raw-dir tmp/ecg_expansion_20261017/raw --mit-raw-dir tmp/multi_record_20261016_01/raw --output tmp/cnn_background_data_check_new.json
& './tmp/cnn_torch_env/Scripts/python.exe' -B model/train/train_cnn_background.py --cache-dir tmp/cnn_background_cache_new --parent-run tmp/cnn_patient_cv_v8_20261017_02 --protocol model/protocols/cnn_causal_background_v10_protocol.json --output-dir tmp/cnn_background_train_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B sim/verify_cnn_background.py --cache-dir tmp/cnn_background_cache_new --parent-run tmp/cnn_patient_cv_v8_20261017_02 --run-dir tmp/cnn_background_train_new --output tmp/cnn_background_model_check_new.json
```

路径和解释器为本机示例。`prepare_cnn_background.py freeze --parent-cache ... --parent-run ... --protocol <新文件>`仅用于新协议，不覆盖已有v10。新机器需要匹配父缓存/权重和已有依赖，不自动安装。

准备器核对官方原始文件、导联首值/模和以及原当前波形逐字节一致；背景检查器独立按窗口末端检索重建全部背景。模型检查器复算采样/患者隔离、逐类/逐患者指标和门槛，重放保存权重。相关源码在src/reference/ecg_causal_background.py与ecg_context_cnn.py，都是自有扩展，来源边界沿用[第三方说明](../third_party.md)。训练/数据/源码/权重哈希与原始logits均保留，实际结果见记录。**smoke未上板测试。**

## 后续只训练支路的对照

[v11协议](../tmp/history/training_handoff_20261017/data/cnn_causal_adapter_v11_protocol.json)复用同一已核对的v10背景缓存，明确绑定其数据协议和清单哈希；保留v10全部结果。`model/train/train_cnn_background_adapter.py`只让context_stem和context_rr的232个参数训练，原主干、RR和分类头全部冻结；保存的每个原参数必须与本折父权重逐字节一致。

v11使用独立种子2026101711、支路学习率0.001、12—25轮/耐心6，保留epoch0。它是后续完整方案比较，冻结、学习率与种子均变化，不能单独归因冻结这一个因素。部署仍有12684个总参数，冻结不等于FPGA可以省去主干；预算门槛继续检查总参数。

```powershell
& './tmp/cnn_torch_env/Scripts/python.exe' -B model/train/train_cnn_background_adapter.py train --cache-dir tmp/cnn_background_cache_new --parent-run tmp/cnn_patient_cv_v8_20261017_02 --protocol model/protocols/cnn_causal_adapter_v11_protocol.json --output-dir tmp/cnn_background_adapter_new
& './tmp/cnn_torch_env/Scripts/python.exe' -B sim/verify_cnn_background.py --cache-dir tmp/cnn_background_cache_new --parent-run tmp/cnn_patient_cv_v8_20261017_02 --run-dir tmp/cnn_background_adapter_new --output tmp/cnn_background_adapter_check_new.json
```

新设计才使用同一脚本的freeze阶段生成新的协议，不覆盖已跑协议。v11仍是原26名开发患者的三折，不能称新独立测试；三折与逐类门槛保持不变。
