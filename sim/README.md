# 仿真与软件验证

从项目根目录运行，输出必须选择新目录，完整日志写tmp/：

```powershell
python -B sim/test_mitdb_100.py
python -B sim/test_ecg_peak_reference.py
python -B sim/check_ecg_reference.py --vivado-bin '<Vivado安装目录>/bin' --output-dir tmp/reference_check_new
./sim/run_ecg_smoke_test.ps1 -VivadoBin '<Vivado安装目录>/bin' -OutputDir tmp/smoke_check_new
./sim/run_rtl_tests.ps1 -VivadoBin '<Vivado安装目录>/bin' -OutputDir tmp/axi_check_new
```

## 2026-10-15目录迁移后复核

- Python 3.14：数据/幅值/匹配5项与候选峰边界4项通过。
- Vivado XSim 2026.1：六组20915周期、每周期15字段一致，精选报告results/reference_layout.json。
- 同版本smoke合成样本/FIFO仿真通过：PASS ECG_SMOKE real samples。
- AXI分离通道、反压、FIFO与非法地址自检通过：PASS AXI split channels。
- 本机完整结果：tmp/layout_check_20261015_02/reference、smoke、axi；对应根tmp/layout_reference_20261015_02.log、layout_smoke_20261015_02.log、layout_axi_20261015_02.log。

第一次受限环境中xelab不能编译生成C代码；获得工具执行权限后在新目录重跑通过，首次失败日志仍保留在tmp/layout_check_20261015_01。工具权限问题不能当作功能结果；本次没有修改设计来规避错误。

参考逐周期对照针对src/reference/ecg_reference.py与原RTL；不适用于候选峰ecg_peak_reference.py。所有仿真均不能替代板上验证。**smoke尚未上板测试。**
