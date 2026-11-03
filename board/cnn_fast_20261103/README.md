# 优化版三核 JTAG 交付

2026-11-03 已板测的 FP32 CNN、INT8 CNN、HGB 匹配组合，包含会话工作灯。实物为正点原子领航者 V2，器件 `xc7z020clg400-2`，Vivado/Vitis 2026.1。旧 `board/cnn_triple_20261103` 和 `releases/latest` 保留，不与本目录交叉混用；本包未验收 Flash 冷启动。

## 校验、运行与查看硬件

在仓库根目录执行，Python/Node/驱动与首次网页安装见[统一教程](../../docs/download_guide.md)：

```powershell
python -B board/cnn_fast_20261103/check.py
& build/build_web.ps1 -SkipInstall
```

`check.py` 校验 8 份产物和 69 项源文件哈希；原构建收据保持原字节，原 tmp 生成输入已映射到本目录 `generated/`。不依赖原作者 tmp 即可校验和加载。

核实 JTAG 启动方式、供电、JTAG 与 USB_UART；关闭串口监视器及网页采集。启动 Vitis 的 hw_server，核实实际电缆序列号、串口和 USB 设备身份，再执行以下命令。命令会复位并临时运行匹配 BIT/ELF，不写 Flash；`--output` 必须是尚不存在的 tmp 子目录。

```powershell
& tmp/web_env/Scripts/python.exe board/cnn_fast_20261103/load.py --xsdb '<Vitis>/bin/xsdb.bat' --cable '<实际JTAG序列号>' --port '<实际COM口>' --device-id '<实际USB设备身份>' --output tmp/fast_load_new
& tmp/web_env/Scripts/python.exe src/web/run.py --port 8000
```

浏览器打开 `http://127.0.0.1:8000`。选择板卡端口，回放 `data/cnn_triple_synthetic500.csv`，选 CNN、INT8、边采边测，并按采样节拍回放。这是合成信号演示，不能称为患者实测。也可用 ADS 接收器另一串口实时采集；本版新增验收使用已采集 CSV 回放，尚无新增无线长时验收。CNN FP32/INT8 整段与实时、HGB 整段功能保留。

Vivado 2026.1 的 Tcl Console 执行以下命令，打开匹配的真实实现快照，查看 Reports 与 Device 页面；不需要连接板卡：

```tcl
source {<仓库绝对路径>/board/cnn_fast_20261103/open_routed.tcl}
```

系统资源、层级与时序报告由脚本生成。资源是静态实现用量，不是运行时负载；切换网页模式不会释放另外两个核。原报告及实测数据见[INT8 优化证据](../../docs/evidence/cnn_int8_fast_20261103/summary.json)。

## 从源码重建

准备 Vivado/Vitis 2026.1 和含 PyTorch、NumPy、SciPy 的模型 Python 环境，参考本目录 `requirements-model.txt`。在仓库根执行：

```powershell
& build/rebuild_cnn_triple.ps1 -Python '<模型环境python.exe>' -Vitis '<Vitis目录>' -Vivado '<Vivado目录>' -Name cnn_fast_rebuild_new -FastWorkLed -Int8Fast -Conv16
```

该入口执行参数导出、HLS、RTL 联合仿真、系统实现和 ARM 构建，不自动下载。输出工程在 `tmp/cnn_fast_rebuild_new/hardware/cnn_pl.xpr`，Vitis 产物在同名目录的 `vitis/`。完整源代码、生成器和权重随仓库提供，`routed.dcp` 用于展示已验证的实现，修改硬件应重新构建。优化阶段已分别构建并板测；组合入口本次做语法检查，未在另一台电脑重新全量构建，不承诺跨主机 BIT 字节或运行时间完全相同。

详细交接数据、报告写作材料和已知边界见[比赛报告素材](../../report/competition_brief.md)。第三方许可沿用[许可说明](../../docs/licenses.md)，项目许可不替代 AMD IP、BSP 与工具生成内容的许可。
