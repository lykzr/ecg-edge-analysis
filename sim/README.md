# 仿真与软件验证

从项目根目录运行，输出必须选择新目录，派生数据写tmp/，需要长期保留的验证日志写docs/records/：

```powershell
python -B sim/test_mitdb_100.py
& './tmp/qrs_env/Scripts/python.exe' -B -m unittest discover -s sim -p 'test_*.py'
python -B sim/check_ecg_reference.py --vivado-bin '<Vivado安装目录>/bin' --output-dir tmp/reference_check_new
./sim/run_ecg_smoke_test.ps1 -VivadoBin '<Vivado安装目录>/bin' -OutputDir tmp/smoke_check_new
./sim/run_rtl_tests.ps1 -VivadoBin '<Vivado安装目录>/bin' -OutputDir tmp/axi_check_new
```

## 验证范围与文档

ecg_reference.py逐周期对照针对现有RTL；v4的软件测试针对当前候选算法，两者不能混用。软件仿真不替代板上验收。

使用说明见上述命令；实验日志、历史通过/失败与准确性评估统一见[文档目录](../docs/README.md)。

分类当前检查采用test_ecg_torch.py、test_cnn_cv.py及verify_cnn_cv.py；原始数据处理另用test_cnn_expanded.py、test_cnn_ltdb.py。旧实验专属测试已随实现归档，不参与当前discover。跨电脑命令与数据边界见[训练交接](../docs/model_training_handoff.md)。
