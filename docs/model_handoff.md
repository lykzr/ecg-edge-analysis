# 模型工程交接入口

当前模型方向为HGB（直方图梯度提升树），早期CNN实验保留供追溯。**目前没有达到全部预定目标的最终模型。** 此次交接的是可检查的研究成果、数值复核材料与集成边界。

## 仓库和分支

- 仓库：`https://github.com/lykzr/ecg-edge-analysis`
- 本地分支：`feature/ecg-model`，由`feature/cnn-model`直接改名，工作内容保留。
- 本次交接仅使用本分支，不合入main。准备阶段检查时远端只有main、system；之后用户已明确批准将这12个文件提交并推送到feature/ecg-model。实际收到的提交号以`git rev-parse HEAD`为准。
- 后续读取本分支不需要合并main。不要直接覆盖队友网页工程或主分支。

## 队友先做什么

1. 阅读[交接检查报告](records/model_handoff_audit_20261031.md)，确认结果及未完成项。
2. 查看[data/model_review说明](../data/model_review/README.md)及[evaluation_summary.json](../data/model_review/evaluation_summary.json)。
3. 使用已有含NumPy的Python，运行以下只读检查；不需要下载数据或重新训练。

```powershell
python -X utf8 -B sim/check_model_handoff.py
```

预期输出包括`passed:true`、`models:3`、`synthetic_rows:160`、`fits:0`、`qualified:false`。这是合成特征数值核验，不是新的准确率测试。

可在另一个目录取得本分支，避免覆盖已有工程：

```powershell
git clone --branch feature/ecg-model --single-branch https://github.com/lykzr/ecg-edge-analysis.git ecg-model-review
Set-Location ecg-model-review
python -X utf8 -B sim/check_model_handoff.py
```

若当前Python没有NumPy，接收方应在自己的隔离环境配置依赖，版本见`data/model_review/requirements.txt`。本次没有替任何人安装。

## 接入队友电脑端工程之前

| 项目 | 本分支研究模型 | 队友ly-Integration中的OpenECG适配器 |
|---|---|---|
| 任务 | 逐拍N/S/VF，连续检测切拍后的评价 | 顶层为记录级节律分类，另返回beats等信息 |
| 入口 | 192维已生成特征；没有直接处理原始mV的本包API | 500Hz单导联mV，至少10秒，仅分析前10秒 |
| 模型来源 | 本项目训练的HGB研究权重 | 调用外部OpenECG预训练能力 |
| 当前可用材料 | 三个外折模型、合成数值向量、实际开发评价摘要 | 网页、后端、数据处理及OpenECG调用代码 |
| 尚需确认 | 正式模型、流式特征契约、INT8/板端及实采 | 最终输出任务、真实设备标度和正式效果验证 |

不能把OpenECG的节律类别直接改名为N/S/VF，也不能把本包塞入其原始波形接口后宣称集成成功。集成先确定最终输出、计算放在电脑还是Zynq、采样率/单位/导联、滤波和时间轴；再实现一种明确的适配器并用同一输入核对。

队友分支的参考审查版本是`wangjianlin-0/health_system-v2`的`ly-Integration`、提交`df9fae6b46d84d91b0cb9f00b4da5fb06b0dbcde`。其代码和文档不自动改变三人团队正式分工。

## 目前的暂停断点

2026-10-31按用户要求复查中断情况：v105/v108共6次分类拟合均已完成并独立核验，未达到全部质量目标；当时最后运行的LUDB200人、4874个峰点输入预检也已完成。没有需要续跑的半截训练，新的形态教师尚未开始拟合。本次未重复训练或启动新实验，自动跟进保持暂停。这里的P/QRS/T是拟研究的内部波形语义，不是把最终心拍任务改成新的三分类。

历史训练、完整数据和缓存重建可继续查原`docs/model_training_handoff.md`及`report/model.md`；它们不属于本次最小数值复核的运行依赖。大量旧实验和本机tmp仍保留，不建议接收方为了集成先重复训练。六名INCART独立患者继续封存。

中断核查详情见[data/model_review/interruption_audit.json](../data/model_review/interruption_audit.json)：17个带状态文件的历史批次均有完整三折结束记录及独立核验；其中5份中间状态未更新，以最终decision与verification为准，历史文件保留。
