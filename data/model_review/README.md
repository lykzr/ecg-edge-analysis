# 心拍模型研究复核材料

本目录用于队友阅读模型结果、核对权重和推理数值。状态为 **RESEARCH_REVIEW_ONLY，尚未达到全部质量目标**，不作为最终生产模型或直接接入网页的分类服务。

## 内容与依赖

- `models/`：v92三个患者外折的HGB（直方图梯度提升树）参数，无pickle的NPZ格式；它们是三个交叉验证模型，没有选定一个生产模型，不默认平均或投票。
- `feature_names.json`：严格按顺序排列的192个输入特征名。
- `synthetic_vectors.npz`：160行固定种子的纯合成特征及三个模型的参考输出，仅核数值；没有患者波形。
- `evaluation_summary.json`：v92/v102/v105/v108历史完整开发集评价摘要及来源SHA，不是合成向量算出来的识别成绩。
- `manifest.json`：文件SHA、类别、来源权重SHA和用途限制。
- `requirements.txt`：本机已验证的最小复核依赖版本。已有NumPy环境可先直接运行；其他版本兼容性需实际核验。

在仓库根目录，用已有含NumPy的Python执行：

```powershell
python -X utf8 -B sim/check_model_handoff.py
```

预期：`passed:true, models:3, synthetic_rows:160, features:192, fits:0, clinical_quality_test:false, qualified:false`。脚本只读，不下载、不安装、不训练；成功只说明文件和合成数值相符。独立目录也可执行该脚本并用`--bundle`指定本目录，不依赖本机tmp、joblib、scikit-learn、WFDB或Torch。

## 输入与集成边界

输入是已经按固定版本生成的192维特征，**不是5000点mV、128点波形或ADC码**。原模型还依赖RR、历史背景、后继RR可用性和无效状态；本目录不生成这些特征，不实现连续检测切拍，也不提供`classify(raw_ecg)`接口。不能把任意192个采样点当作特征。

类别是N、S、VF；VF表示原V/E/F合并，不表示心室颤动，N也不等于临床健康。源码中保留的CNN属于早期实验，当前这组参数来自HGB。

这里选择v92用于数值复核是因为它已有独立导出证明，并不表示它优于所有版本或已通过验收。v57冻结研究参照不因此替换。最新两组v105/v108同样未通过全部目标；见项目[交接入口](../../docs/archive/analysis/model_handoff.md)及[检查报告](../../docs/archive/records/model_handoff_audit_20261031.md)。

## 来源与许可

参数由本项目既有训练导出；训练阶段使用scikit-learn，复核阶段只需NumPy。代码依仓库`LICENSE`；保留依赖各自许可。研究数据来源为PhysioNet的[MIT-BIH](https://physionet.org/content/mitdb/)和[INCART](https://physionet.org/content/incartdb/)，本目录不打包原始数据、患者波形或原资料盘。来源哈希用于追溯，不代表独立测试、真实ADS输入、INT8或FPGA验证已经完成。
