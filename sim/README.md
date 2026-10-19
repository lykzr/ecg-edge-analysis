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

## PC监视器与串口适配验证

只使用Python标准库；隐藏窗口检查另需Tkinter。以下输出目录必须不存在：

```powershell
python -B -m unittest discover -s sim -p test_pc_monitor.py
python -B -m unittest discover -s sim -p test_pc_serial.py
python -B src/pc/ecg_monitor.py --ui-self-test --output-dir tmp/pc_ui_new
python -B src/pc/ecg_monitor.py --headless --demo --seconds 10.01 --output-dir tmp/pc_demo_new
python -B src/pc/ecg_monitor.py --headless --replay tmp/pc_demo_new/raw.log --output-dir tmp/pc_replay_new
```

测试覆盖流解析、坏行恢复、序号回绕/缺口、会话、未知值、容量保护与原文重放；隐藏窗口仅核对控件和绘图对象，不代表人工操作或串口验收。使用说明见[PC监视器](../docs/pc_monitor.md)。

test_pc_serial.py使用假驱动检查Windows结构/配置、读取上限、空读、驱动错误、句柄清理、分块接收/回放、半行断连、记录限额，以及隐藏窗口连接/停止/重连。不会打开实际COM端口；真实驱动、拔插、持续吞吐和板端联调另验。隐藏窗口用例另检查界面状态（未开始/等待/接收/停止/出错/演示/回放）及不同Canvas尺寸下图元不越界；没有Tkinter时这3项跳过。

## PS流式核心验证

```powershell
python -B -m unittest discover -s sim -p test_ps_stream.py -v
```

需要已有GCC（可设ECG_HOST_CC），编译实际src/ps/ecg_stream/stream.c。stream_host.c注入假计时器/AXI/FIFO/UART，由现有PC解析器检查分块输出，覆盖正常/末批、慢速丢弃、超期停止、UART停滞及启动拒绝。输出保留在tmp/ps_stream_tests的独立目录，编译器临时目录也仅作用于该子进程；不自动清理、改权限或安装编译器。假FIFO不执行QRS，真实驱动、节拍、事件和板上运行须另验；入口见[PS说明](../docs/ps_stream.md)。

## 克隆后完整性与已选对照

```powershell
python -B sim/check_checkout.py
python -B sim/check_training_checkout.py
python -B sim/check_baseline.py
python -B sim/check_baseline.py --metrics
python -B sim/check_baseline.py --cache-dir tmp/cnn_git/cache --replay-weights
```

前三项是标准库静态/哈希检查；后两项分别需要NumPy和Torch，使用已有独立环境，不自动安装。checkout_files.json明确列出当前源码/协议、工程与基线依赖；新增正式入口时随修改维护，不能只看本机文件存在或哈希通过就称已提交共享。算法/QRS测试与RTL逐周期入口保持独立，派生缓存由脚本重建。

## ADS1292R离线字节解码

```powershell
python -B -m unittest discover -s sim -p test_ads1292.py -v
```

仅需标准库；覆盖SPI状态/24位补码和显式版本的厂商偏移码帧，不打开设备或实现自动同步。格式、来源冲突和待核项见[ADS1292R说明](../docs/ads1292.md)。合成向量通过不代表真实ADC采集或PS流式程序已上板。

PS流式测试默认500Hz，并单独核对360Hz兼容参数。RTL合成/FIFO检查可运行`./sim/run_ecg_smoke_test.ps1 -VivadoBin '<Vivado安装目录>/bin' -OutputDir tmp/rtl_500_new -SampleRate 500`；不传SampleRate仍为原smoke的360Hz。两种参数均不代表真实节拍或板上通过。

## 电脑→Zynq输入与双向中转

```powershell
python -B -m unittest discover -s sim -p test_ecg_bridge.py -v
```

使用已有GCC编译正式src/ps/ecg_bridge/bridge.c为测试共享库，注入受控串口与原检测器500Hz软件参考AXI；测试CLI厂商文件/模拟实时入口及协议错误，不操作板卡。产物保留tmp/usb_bridge_tests/独立目录；回调异常必须失败，不能由ctypes忽略后当成功。说明见[中转入口](../docs/bridge.md)。
