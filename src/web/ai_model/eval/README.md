# 离线指标辅助

model_eval_report.py读取真实预测列表，计算逐类precision/recall/F1、混淆矩阵及macro-F1；不运行或训练模型。手写样例只验证计算，不能作为真实精度。生成的合成开发数据也不能当独立患者测试。

从项目根执行：

```powershell
python -B src/web/ai_model/eval/model_eval_report.py tmp/predictions.json
```

predictions.json为非空列表，每项含true_label与predicted_label。报告须保留来源、患者划分、预处理和模型版本。本目录不用于自动接通本项目模型分支，见[模型合并计划](../../../../report/model_merge.md)。
