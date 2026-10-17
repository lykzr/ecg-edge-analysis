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

## PC离线监视器验证

只使用Python标准库；隐藏窗口检查另需Tkinter。以下输出目录必须不存在：

```powershell
python -B -m unittest discover -s sim -p test_pc_monitor.py
python -B src/pc/ecg_monitor.py --ui-self-test --output-dir tmp/pc_ui_new
python -B src/pc/ecg_monitor.py --headless --demo --seconds 10.01 --output-dir tmp/pc_demo_new
python -B src/pc/ecg_monitor.py --headless --replay tmp/pc_demo_new/raw.log --output-dir tmp/pc_replay_new
```

测试覆盖流解析、坏行恢复、序号回绕/缺口、会话、未知值、容量保护与原文重放；隐藏窗口仅核对控件和绘图对象，不代表人工操作或串口验收。使用说明见[PC监视器](../docs/pc_monitor.md)。

## 克隆后完整性与已选对照

```powershell
python -B sim/check_checkout.py
python -B sim/check_training_checkout.py
python -B sim/check_baseline.py
python -B sim/check_baseline.py --metrics
python -B sim/check_baseline.py --cache-dir tmp/cnn_git/cache --replay-weights
```

前三项是标准库静态/哈希检查；后两项分别需要NumPy和Torch，使用已有独立环境，不自动安装。checkout_files.json明确列出当前源码/协议、工程与基线依赖；新增正式入口时随修改维护，不能只看本机文件存在或哈希通过就称已提交共享。算法/QRS测试与RTL逐周期入口保持独立，派生缓存由脚本重建。
