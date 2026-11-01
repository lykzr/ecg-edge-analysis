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

板端原事件与电脑模型事件只在±25点（50ms）内双向唯一时关联，双方位置和差值保留，不拟合偏移或给未关联事件强填类别。关联不是专家标注检测精度；板端NO_MODEL/?仍保留，页面明确标为电脑HGB。尚未进行真实ADS整机验收、ARM移植、INT8/PL或最终模型质量验收。

模块中的docs/records及evidence保留原ZIP时的研究报告/来源快照，其中旧src/model_inference是当时来源路径；当前可执行位置统一为model/inference。本次合入的范围和实际检查见[集成记录](evidence/model_integration_20261101.md)。

电脑端网页接线的实际验证、失败与剩余边界见[联调检查报告](evidence/hgb_web_integration_20261101.md)。
