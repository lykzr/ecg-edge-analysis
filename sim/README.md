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



克隆完整性运行python -B sim/check_checkout.py；历史基线清单允许Windows反斜杠，检查脚本按相对目录分隔符统一换算，并保留目录边界校验，不修改基线清单字节或哈希。针对性检查为python -B -m unittest discover -s sim -p test_checkout.py -v，覆盖POSIX拆分规则、Windows/双反斜杠、绝对路径/盘符/越界拒绝和当前清单哈希。Windows上的规则测试不等于Linux/macOS原生运行验收。



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



计时回归同时编译正式bridge_time.h，用无括号的BSP频率宏模拟调用处求值，检查两秒边界和长期tick→微秒一致性；不改变频率/预分频或用假时钟推断实物抖动。实际CLOCK_REVERSED定位和数字回放见[实板修复记录](../docs/records/bridge_board_20261020.md)。



## 厂商CSV与独立采集视图



```powershell

python -B -m unittest discover -s sim -p test_pc_capture.py -v

```



标准库检查覆盖五列RawData、偏移码恢复、原文保存、候选起始对齐/锁定后错误、尾部/限额/驱动异常、端口身份变化和双通道绘图几何；Tk可用时验证隐藏采集窗口及主入口。缺Tk只跳过隐藏窗口用例，不把跳过当作人工视觉验收。产物保留tmp/pc_capture_tests/独立目录；不打开实物端口、不运行模型或板端程序。



## UI目录与启动回归



界面位于src/ui，后台位于src/pc；从项目根运行python -B src/ui/main.py，旧入口仍兼容。python -B -m unittest discover -s sim -p test_ui_layout.py -v检查新旧入口从其他工作目录启动、无界面输出一致、后台不依赖CLI/UI/Tk和隐藏窗口自检；它不打开真实串口，不代替人工视觉或新的上板验收。



## 端口识别与界面中转



```powershell

python -B -m unittest discover -s sim -p test_pc_bridge.py -v

```



使用已有GCC、标准库及Tk；覆盖USB实例跟随COM变化/缺席/复用、歧义和角色冲突、身份保存、CSV与34字节双源中转、实际PS C核心与软件参考AXI的假双串口回传、记录原件、有限点数、手动停止收尾、断连、超时、记录限额和队列满；隐藏窗口仅检查构造/入口，不替代人工显示验收。测试保留tmp/pc_bridge_tests/，不打开真实端口。使用说明见[界面送样](../docs/bridge.md#界面送样)。



## 输入诊断与500Hz滤波回归



python -B -m unittest discover -s sim -p test_capture_analysis.py -v检查能量死区、常量平移、脉冲事件和CSV来源/拒绝覆盖。test_ecg_filter_reference.py另核对500Hz/50Hz差分方程；不操作板卡或评估无标注准确率。实物有限验证入口board/verify_ecg_bridge.py须显式USB身份，运行前另行授权并启动匹配应用。



## 系统发布与历史回归



python -B sim/check_system_release.py --repository .核对latest文件、两套XSA内嵌bit、源码/ELF及精选数字实板原文；python -B sim/check_smoke_release.py默认检查latest/smoke。旧smoke归档清单原字节保留，当前三个迁移工具发生的历史哈希差异明确列出，核心RTL/main.c/ELF/硬件/验收证据仍必须一致。python -B -m unittest discover -s sim -p test_system_release.py -v检查路径边界、损坏拒绝、复制后演示/新旧回放/隐藏窗口及包内工作区参数。测试不连接板卡；运行产生的日志放tmp，不把本机复制当另一台电脑实测。



## 启动学习候选检查

python -B -m unittest discover -s sim -p test_qrs_auto.py -v检查预热、幅值/极性、静默、复位/暂停、因果、定点界限和显式检测器身份。check_qrs_auto.py用现有XSim逐周期核对候选RTL/整数参考，并复跑已知开发记录；需要已有Vivado及本机输入，参数见脚本帮助。原检测器与smoke独立保留；离线/构建通过不等于上板或准确性通过，详见[候选说明](../docs/qrs_auto.md)。


候选开发期间，已验latest的PC源码仍是冻结旧版；check_system_release.py不传--repository时检查其自身完整性与旧验收证据，传--repository才另外要求正式源码也完全一致。QRS-AUTOPEAK兼容改动尚未发布时，后者及test_system_release的对应严格源检查会报告差异，不能改旧清单或放宽断言伪装通过。当前预期差异和边界见[修复记录](../docs/records/qrs_auto_20261021.md)。check_auto_bridge.py独立核对候选实际PS C的允许改动与离线双向闭环，不取代该发布检查。


## 原波形确认候选

python -B -m unittest discover -s sim -p test_qrs_peak.py -v检查360/500Hz、原波形位置/RR、宽波/双相/快速真心拍、暂停/复位、因果和尾部。data/evaluate_qrs_peak.py完整复跑19条已知开发记录并核对基线来源，参数见[说明](../docs/qrs_peak.md)。当前仅软件，不继承旧候选RTL/bit/实板成绩；失败滤波和平方核心已归档tmp，不能称准确性通过。


## 成熟QRS独立候选

在data/requirements_qrs.txt指定环境运行python -B -m unittest discover -s sim -p test_qrs_v5.py -v，检查原码平台、40Hz候选支路、正负/快速/弱尖/宽波/双相、暂停/复位、未来/过期读取和前缀/尾部。完整已知记录回归另由data/benchmark_qrs_v5.py执行；软件检查不代表500Hz、整数RTL或上板通过，见[说明](../docs/qrs_v5.md)。
