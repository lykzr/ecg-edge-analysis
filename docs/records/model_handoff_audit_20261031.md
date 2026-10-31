# 模型工程交接检查报告

日期：2026-10-31（北京时间）。用途：三人项目内部阅读、集成讨论与研究数值复核。结论：**可交接研究材料；未通过最终模型质量验收，未完成端到端产品集成。** 本报告不是医疗检测报告或产品合格认证。

## 1. 版本、分支和共享状态

- 仓库：https://github.com/lykzr/ecg-edge-analysis
- 本地分支已按用户要求从feature/cnn-model改名为feature/ecg-model；名称变更保留所有工作，不改模型内容。
- 当前HEAD及本地main均为c6337c954fd35260fd607421ad455f755a28284e，本次没有切换/提交/合并/推送main。
- 本次通过GitHub只读API检查：远端列出main、system，尚无feature/ecg-model；远端main为c68f4b9529934909a7fed118b59353376d3eba7b。本地origin/main仍是旧缓存，没有fetch、pull或merge，不声称已同步主分支。
- 远端新main包含协议搬到data/protocols、记录/发布目录整理和主体更新；与本机部分旧文件存在路径差异。接收者应单独检出模型分支阅读，不用本分支整包覆盖新main或队友网页仓库。
- 整理前已有884项工作区变更，本次未全量暂存或归属认领；本报告末尾列出独立最小提交范围。该段描述准备阶段快照；用户后续已批准该范围的提交推送，云端实际版本以分支提交为准。

## 2. 当前模型与交接范围

当前研究以HGB（直方图梯度提升树）为主，不是CNN；旧CNN为历史实验。公开输出目标仍为逐拍N/S/VF；VF指V/E/F合并，不能解释成心室颤动，N也不是临床健康结论。

本次整理的data/model_review含v92三个患者外折模型的只读NPZ参数、192列名称、160行纯合成特征及参考概率/预测、历史完整评价摘要和SHA。选择这组是为了复用已证明的导出链路，**不是选定最新最优生产模型**；没有默认选择一折、平均或投票规则。v57冻结研究参照不变。

实际新模型训练次数为0。没有添加原始心电数据、患者波形、官方资料、虚拟环境、密钥、板卡镜像、训练缓存或全部历史tmp。三个权重已逐文件对照原导出SHA，160行合成数值另与原scikit-learn模型概率和预测核对。训练用过的患者数据不会因此变成新独立测试。

## 3. 实际识别成绩

以下摘自已完成且独立核验通过的完整开发评价：61条INCART记录、26开发患者、143916个原选心拍；两种输入共122流/284685自动事件/3660分钟。表内只比较同新C位置与真实C重切的hp05模式，单模式1830分钟；没有重新运行训练或本轮完整记录评价。结果已看过并反复用于开发，**不是未触碰独立测试**。

| 版本 | 输入维数 | VF TP/FP/FN | VF精确率/召回率 | S精确率/召回率 | macro-F1 | F命中/161 | 分钟MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| v92 | 192 | 15879/1259/532 | 92.6538%/96.7583% | 53.7086%/81.6313% | 0.861196 | 107 | 0.890164 |
| v102 | 207 | 15899/1241/512 | 92.7596%/96.8801% | 54.5575%/82.1618% | 0.864257 | 104 | 0.869399 |
| v105 | 208 | 15874/1269/537 | 92.5976%/96.7278% | 53.8696%/82.1618% | 0.861953 | 107 | 0.897268 |
| v108 | 208 | 15881/1258/530 | 92.6600%/96.7705% | 53.3218%/81.9629% | 0.860615 | 107 | 0.890710 |

全部版本都未满足原完整目标。VF总体精确率/召回率要求各≥98%，S各≥90%、N各≥95%、macro-F1≥90%；还包含各折、支持数足够的患者逐类、F召回≥80%、VF分钟MAE≤0.4、最坏分钟误差≤15及表预算262144B。不能从不同版本挑选优点拼成合格模型。

v108完整hp05混淆矩阵及逐类/各折/各患者/原F等结果随evaluation_summary.json保留；未检测参考和无效输入仍计入缺失，没有通过删困难患者或改标签提高分数。v105/v108各新增3fit均完成但未晋级。S类、融合心拍和部分患者仍是主要风险。六名INCART独立患者继续封存。

## 4. 检查项目与判定

| 检查 | 判定及边界 |
|---|---|
| 分支与主分支隔离 | 本地改名已完成；main提交号未变；无commit/push/merge |
| 老Git训练源码检查 | sim/check_training_checkout.py本机通过，仅覆盖其列出的早期CNN入口，不证明近期HGB全链路从零可重建 |
| 既有v99复核 | 本机重跑通过，2500固定请求、9个模型、纯NumPy、0fit；已查看数据，仅作已有数值复核 |
| 本轮最小包 | 三份v92权重与原SHA一致；160组合成特征与原joblib概率/类别一致；最终文件SHA见data/model_review/manifest.json，隔离目录结果见本报告末尾 |
| 脱离本机tmp | 新sim/check_model_handoff.py只需NumPy和data/model_review；隔离目录复制后复查，不依赖训练库或本地缓存 |
| 完整准确率 | 历史独立复算已完成；本轮没有新独立性能测试；原质量标准未通过 |
| 最新暂停断点 | LUDB200人24MB原生数据已核100万II采样；1830个完整C窗口与Python完全相同，4874个P/QRS/T局部特征独立复算差0，尚未训练教师 |
| 真实ADS/网页集成 | 未在本轮运行实采或接入队友网页；接口和输入差异待联调 |
| INT8/ARM/FPGA | 未完成本轮模型的整数/硬件数值、资源、时延及板上验收 |
| Git可见性 | 准备阶段尚未提交推送；用户后续批准仅推送12项，接收者以远端实际提交和运行结果为准 |

复核环境：Windows，Python3.12.6、NumPy2.2.6；原模型对照还用scikit-learn1.7.2。接收方最小数值复核不需要scikit-learn。FPGA工具目标仍为Vivado/Vitis2026.1，本轮未启动构建或板卡写入。

LUDB是下一方法研究的准备数据；197条完整边界、95/104/111边界异常显式未知；4874个峰点全部保留。形态教师P/QRS/T与最终N/S/VF任务不同，不能把输入预检成功写成模型精度提升。原先线性教师只是草案，后续小HGB教师也尚未拟合。训练和自动跟进保持暂停。

## 5. 与队友OpenECG工程的关系

按此前只读核查的health_system-v2/ly-Integration提交df9fae6b46d84d91b0cb9f00b4da5fb06b0dbcde：其适配器用500Hz单导联mV、前10秒调用OpenECG，顶层task_type为record_level，并返回beats等字段。这里的权重要求192维已生成特征，不能直接替换其原始波形接口。其仓库的一次公开样例分类跑通不是本模型验证证据，也不能代替正式效果测试。

先确认最终输出是整段节律还是逐拍类别、计算在电脑或Zynq、输入标度/导联/滤波/时间轴/无效语义，再做适配与同输入复核。当前不声称把两工程拼起来就已完成整机，也不因为现有OpenECG而默认取消本人模型验证任务。

## 6. 最小复核步骤

先看docs/model_handoff.md，然后在仓库根目录用现有NumPy环境运行：

```powershell
python -X utf8 -B sim/check_model_handoff.py
```

预期包含passed:true、models:3、synthetic_rows:160、fits:0、clinical_quality_test:false、qualified:false。合成特征没有真实生理意义；通过只证明数值和文件完整，不能计算患者识别准确率。

全部原始实验、失败、未完成事项和本机源证据均保留，没有清理。更完整历史可在本机report/model.md与docs/records查阅；它们不是这12个最小文件的运行依赖。

## 7. 待提交范围与发送说明

建议先只提交下列12个自包含文件，不使用git add .，不自动把884项既有变更混入提交：

- `data/model_review/README.md`
- `data/model_review/evaluation_summary.json`
- `data/model_review/feature_names.json`
- `data/model_review/manifest.json`
- `data/model_review/models/v92_fold0.npz`
- `data/model_review/models/v92_fold1.npz`
- `data/model_review/models/v92_fold2.npz`
- `data/model_review/requirements.txt`
- `data/model_review/synthetic_vectors.npz`
- `docs/model_handoff.md`
- `docs/records/model_handoff_audit_20261031.md`
- `sim/check_model_handoff.py`

建议提交信息：`docs(model): prepare research handoff and reproducible numeric checks`。提交与推送仅面向feature/ecg-model，是否合入main由团队以后决定。准备阶段未执行提交或推送；之后用户已依据工作区writing-block.md第4.3节明确批准，只提交推送这里列出的12个文件到feature/ecg-model。旧修改过的导航/计划/历史日志另外保留，本轮最小包不依赖它们。

推送后可转发：仓库lykzr/ecg-edge-analysis，分支feature/ecg-model，先读docs/model_handoff.md和本报告；目前为HGB研究结果及数值复核，尚无最终合格生产模型，不能直接替代OpenECG原始波形接口。

## 本轮执行后的复核结果

- 既有v99：2500条已查看固定请求、9个模型只读复查通过，0fit，qualified:false。
- 当前最小包：本机160行合成特征×3个模型通过；原joblib概率/类别一致。
- 隔离目录：只复制上述12个文件，以Python -I -B运行，通过相同检查，且确认sklearn/joblib/WFDB/Torch均未加载。没有第二台电脑实测。
- manifest中每份权重/输入/摘要/说明均有SHA；160行合成输入不含患者波形。本次没有重新训练或重新执行完整识别评价。

```json
{"passed": true, "models": 3, "synthetic_rows": 160, "features": 192, "fits": 0, "clinical_quality_test": false, "qualified": false}
```

## 用户批准后的提交边界

用户已明确同意把列出的12个文件提交并推送到feature/ecg-model；不会合入main，也不会提交884项既有工作区改动。前文远端分支不存在、HEAD提交号和未提交状态均为准备阶段快照。云端接收版本以Git提交记录为准，发布研究复核材料不代表模型质量验收通过。

跨平台文件校验：为避免Windows Git自动CRLF换行使正确文本误报SHA错误，说明/JSON/依赖清单按LF标准化后校验；模型和合成NPZ仍严格逐字节校验，不忽略参数或实际文本内容变化。
