# merge分支的模型接入入口

完整研究模块位于[model/inference](../model/inference/README.md)，已包含从500Hz单导联mV到自动检测/切拍、192项特征和N/S/VF分类的代码、必要常量、三份v92权重、C源码和Windows x64主机程序。克隆merge后不需要旧作者tmp或另一个ZIP才能运行合成自检。

## 运行

使用具备NumPy2.2.6、SciPy1.16.2的Python3.12环境，在项目根运行：

```powershell
python -X utf8 -B model/inference/check.py
python -X utf8 -B model/inference/run.py --input model/inference/examples/synthetic500.csv --fold 0 --preprocess hp05 --output tmp/model_beats.csv --features tmp/model_features.npz
```

已有输出拒绝覆盖，请换新文件名。Windows x64已附程序，不需要为了运行安装GCC；源码重建方法见模块README。依赖与网页Python3.14环境分别管理，不自动在现有网页环境降级/安装模型依赖。

先读[固定配置与患者分折](../model/inference/docs/integration_profile.md)，机器可读配置为[integration_profile.json](../model/inference/integration_profile.json)。当前明确fold0、hp05、原始mV；正式生产模型尚未决定。

## HGB类别与质量门槛的来源核查（2026-11-01）

当前v92的[配置](../model/inference/config.json)只明确N/S/VF三类及VF为原V/E/F合并，没有给出N或S的完整原始标注符号映射。已交付推理源码、评价摘要及模型分支交接材料不足以确认N是否仅为原始正常心拍，或还合并其他心拍。旧CNN的`model/prepare/prepare_cnn_expanded.py`虽然写有N←N/L/R/j/e，但不能用作HGB映射证据；当前不得据此解释HGB的N。应补查原HGB标签生成脚本及其实际训练缓存映射。N预测也不能单独推出整段心电或受测者健康。

当前生效标准为[90%工程验收配置](../model/hgb_quality_policy.json)，由用户于2026-11-01明确指定。N、S、VF各类精确率/召回率、macro-F1及各折对应比例统一≥90%；原F子类召回率单独采用≥75%。患者逐类比例同为90%，但支持数下限未查实，患者项待确认，不自动通过。分钟计数MAE≤0.4拍/分钟、最坏绝对误差≤15拍、树表估算≤262144字节不是比例，保持原值。

旧门槛及修改前资料已按原字节、SHA256和路径映射归档到本地 docs/archive/hgb_quality_before_90_20261101/。冻结模型包和研究包中的旧quality_checks、qualified及文字只作为来源快照，不参与当前判定；原成绩及来源封印保留。当前判定见[新版重判证据](evidence/hgb_quality_90_20261101.json)。

既有v92 hp05三折开发成绩重判：N和VF总体精确率/召回率通过；S精确率53.71%、召回率81.63%、macro-F1为86.12%、原F子类召回率66.46%仍未达到75%。分钟MAE为0.890164、最坏少计54拍仍未通过，树表208056字节通过。患者项未完备，整体仍不通过。没有重跑完整准确率，也不是当前部署fold0的新独立测试。

比例标准用于有专家标注的评价集统计，不表示单拍模型概率达到90%就已证实数据正确，也不直接判定健康。

## 系统调用边界

后端需要时可把model/inference加入独立模型进程的模块路径，导入adapter.analyze_ecg，显式传fold/preprocess。该函数返回JSON安全的逐拍结果，第一拍RR未知/不完整窗保留UNCLASSIFIED，不用N替代失败。完整输入和时间定义见[接口说明](../model/inference/docs/integration.md)。

网页现在默认注册hgb，显式ECG_MODEL_TYPE=none仍关闭分类，openecg保留为另一项节律适配。HGB每次在独立进程处理完整连续记录，不把实时数据块独立推理后拼接。固定模型和预处理不变，不训练，不替换固件。

## 网页与采集流程

网页环境已有NumPy/SciPy时可使用当前Python，但应先运行上面的完整check.py。已验证模型环境为Python3.12/NumPy2.2.6/SciPy1.16.2。网页使用其他环境时，在src/web/.env配置：

```text
ECG_MODEL_TYPE=hgb
ECG_HGB_PYTHON=<已通过模型check.py的Python可执行文件>
```

缺环境时，在获得安装授权后，用Python3.12创建独立虚拟环境，并安装model/inference/requirements.txt；不降低或替换网页现有Python。重启网页服务并重新构建前端，命令见[网页启动](download_guide.md)。启动时不会自动安装或下载模型。

在“实时与板卡”选择厂商CSV、蓝牙采集或其Zynq中转模式，默认勾选“采集结束后自动提交完整记录分析”。后台等待来源、串口和文件关闭后读取完整samples.csv；CH2原码按现有2.42V/增益6合同换算mV，再用模型hp05。不会读取厂商滤波列、网页零相位滤波或4096点显示缓存。点击“查看模型分析进度与逐拍结果”可看N/S/VF数量、未分类、R位置、概率及板端事件关联，完整逐拍结果可导出记录JSON。

标准500Hz→Zynq须明确选择“未滤波→hp05”或“已匹配0.5Hz因果高通→raw”；不清楚时拒绝模型分析。它的规范int16/4096输入不套ADC转换。360Hz、演示、日志和只收板端结果不自动推断为可用模型输入。已有历史会话可点“分析已保存记录”；重复提交复用原任务，服务重启后保留已保存任务号。

每条记录最多200000点（500Hz约400秒），超限拒绝而不截断。原码索引/时间必须连续，板卡中转还须DONE且来源/确认/回显数量一致；错误、缺文件、缺样或保存失败会拒绝。来源没有每样本硬件序号时，不能据此证明无线零丢样。重连、导联/增益切换或未知时间缺口需开新采集会话；整段模型每次重置滤波、检测、RR和历史状态。

板端原事件与电脑模型事件只在±25点（50ms）内双向唯一时关联，双方位置和差值保留，不拟合偏移或给未关联事件强填类别。关联不是专家标注检测精度；已发布固件NO_MODEL/?仍保留，页面明确标为电脑HGB。独立ARM候选的受控实测见下节；尚未进行真实ADS整机、INT8/PL或最终模型质量验收。

## Zynq ARM移植入口

可移植C11核心在[src/ps/ecg_hgb](../src/ps/ecg_hgb/README.md)，复用上述固定fold0权重与模型自身的检测/重切拍，不重新训练。已实现完整整段特征和分类，主机对齐与Cortex-A9静态库构建结果见[证据](evidence/hgb_arm_20261101.json)。导出器、主机对照和交叉构建分别为`build/export_hgb.py`、`sim/check_hgb_arm.py`、`build/build_hgb_arm.py`；输出到新tmp目录，可脱离旧派生产物重建。

现已新增独立Vitis裸机自检与串口批处理候选，复用匹配smoke硬件，hard-float、256KB栈及静态DDR，实际通过ARM逐特征/概率核对和两轮各30000点USB_UART送样。精选证据见[ARM实板核验](evidence/hgb_arm_board_20261101.json)，构建/下载/电脑送样入口见ARM核心说明。`HGB-BATCH-1`严格独立于既有输入/结果协议，仅接500Hz单导联mV，最多30000点、480拍；不是厂商34字节解析入口。

双协议候选现已接入网页`board_model=true`，保留原实时QRS。网页板载模式完整接收至多30000点，再按HGB-BATCH-1送到ARM；页面标明zynq_arm与模型身份，独立保存全部心拍/概率。普通电脑报告分析仍是host_pc，可以分别启停；不能混称。已用标准500Hz与厂商格式受控数据验证实际ARM结果，并在同一固件中切回原实时QRS，无需复位。实际证据与Flash/发布状态集中在[当前报告](../report/report.md)。

该候选仍按完整记录计算，未完成连续有界模型调度。首RR未知、末端不完整窗继续保留未分类；模型自身重切拍的事件编号不套用原QRS编号。页面板载模式波形来自电脑送板输入，不能称板端回显；完整记录的确认与三类结果单独核对。本轮不提供真实AFE准确率、最终模型质量或FPGA加速结论。

模块中的docs/records及evidence保留原ZIP时的研究报告/来源快照，其中旧src/model_inference是当时来源路径；当前可执行位置统一为model/inference。本次合入的范围和实际检查见[集成记录](evidence/model_integration_20261101.md)。

电脑端网页接线的实际验证、失败与剩余边界见[联调检查报告](evidence/hgb_web_integration_20261101.md)。

Zynq实物数字回放已按两条完整记录验证；输入、逐点回显、R峰/RR及电脑模型结果的具体证据见[实物联调报告](evidence/hgb_board_integration_20261101.md)。真实ADS输入仍需接模块另验。
