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

这是整段研究入口；运行网页不会因为文件合入就自动加载HGB。网页已有factory默认none、可选OpenECG行为保持。实时状态、丢样重置、Zynq事件和模型侧重心位置的对应由系统集成另验，不伪造板上分类通过。没有最终合格模型、INT8/PL/真实ADS整机质量验收。

模块中的docs/records及evidence保留原ZIP时的研究报告/来源快照，其中旧src/model_inference是当时来源路径；当前可执行位置统一为model/inference。本次合入的范围和实际检查见[集成记录](evidence/model_integration_20261101.md)。
