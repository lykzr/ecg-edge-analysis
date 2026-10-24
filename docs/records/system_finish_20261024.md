# 系统一致性修复、完整重建与负载边界

## 范围

2026-10-24用户授权修复五处代码不对应，完成单命令构建收口、500Hz通信压力检查及实际应用/FSBL许可核对。未授权新板卡操作，本轮不打开串口/JTAG、不写Flash、不训练CNN、不调QRS规则，不替换latest或操作Git。保留根README、资料索引、冻结模型与QRS数学来源。

## 五处修复

1. board/runtime_artifacts.py从实际构建清单提取唯一bit/XSA/初始化/ELF并验证SHA，verify_runtime和verify_runtime_faults使用这些路径，不再校验新文件却下载旧latest。现有360验收脚本拒绝500清单；不能冒充500实板入口已完成。
2. RuntimeWorker在DONE后检查当前接收残行。内存复现的旧行为是completed/error=None/incomplete_rx_bytes=3；新行为failed并保存错误。仍不宣称能证明DONE之后未来永远没有异常字节。
3. 板端T重复最近事件的心率/RR；旧行为60次/分、1000ms被周期T清成未知，新360/500实际C链路回归检查结束T保持一致。无已知RR仍为-1，新鲜度仍由合法波形判断，不凭周期状态证明活跃。
4. 重建显式--rate/-Rate选择360/500，覆盖继承环境并检查清单sampling_hz。模拟子进程用环境500、显式360检查通过；不是实际360硬件重建。
5. draw_trace的脚注接收实际采样率，中转调用传入rate，360/500均由内存绘图检查核对。不是新界面人工视觉验收。

## 软件与仿真检查

已有Python3.14.7、NumPy2.4.4、SciPy1.18.1、WFDB4.3.1、GCC、Tk。正式清单复制到无历史tmp副本后，17组检查/133项测试通过，日志tmp/system_finish_20261024/clean_regression。实际C500七项、C360六项及新一致性四项也单独通过。检测数学、源窗口与原门槛未修改，未重新声称新患者独立准确性或105噪声合格。

## 500Hz压力与明确限制

sim/check_rate500_load.py编译当前实际C链接/处理流程，虚拟UART按115200/8N1、两向各11520字节/秒、64字节板端FIFO、8192字节固件发送队列和默认4096点电脑源队列推进。1ms服务步长是模型假设，不是ARM执行耗时。输入是固定数学合成信号，不是实采，也不把合成心拍事件数作为临床准确率。

探索load01发现100/500ms读节拍积压失败，未提高队列/带宽来掩盖。load_final共13种情况：12个正常完成/预期明确拒绝条件成立，另1个窗口跟踪高负载失败作为诊断对照，不算正常吞吐通过。120/180/240次/分各30秒、500ms集中源数据、10ms读节拍30秒完整收发；同输入的事件位置/RR与正常负载一致。240次/分正常服务120秒共60000点、477事件、源队列峰37点、发送队列峰366字节；虚拟事件最大送达延迟约0.680秒，包含因果检测/切拍等待及虚拟传输，不是实板计算时间。

100ms和500ms慢读分别约22.794秒、10.346秒触发4096点源队列上限；10ms读节拍在30秒内能完成，但长测约215.936秒同样积压失败，不能因为短测通过便宣称可长期500Hz。另覆盖源队列容量不足、PC接收缓冲溢出、固件UART_STALLED/客户机就绪超时，均明确失败而非静默丢样。

每拍完整窗口十六进制跟踪在240次/分约27.968秒触发队列上限。main默认ECG_RUNTIME_TRACE=0，构建可显式开启1，只用于逐窗口数字验收；verify_runtime会拒绝用关闭跟踪的新镜像声称完成窗口比对。没有改W/E字段、批次32点或一包在途协议。

完整压力输入/源码/执行文件证据及逐例JSON在tmp/system_finish_20261024/load_final；早期load01/load02保留。真实USB调度、ARM算力、无线、物理拔插和真实持续记录仍未验；默认64MiB记录限额仍适用。

## 完整构建过程

Python封装首次在tmp/c24发生RTL层次解析失败，未归因算法或安装损坏。新增原生PowerShell单入口，在正式清单副本tmp/c25从头完成BD/综合/实现/bit/XSA/初始化，建立/保持裕量0.329/0.057ns，布线DRC0；软件随后发现新增两个CMake编译选项被拼接成off-DECG_RUNTIME_TRACE=0，明确失败、没有成功清单。修正为带引号的CMake字符串，失败目录保留。

正在tmp/c26新的正式清单副本从零重跑board/rebuild_system.ps1；初始无tmp，不复用c25硬件/工程，仅外部解释器和已安装工具可用。后续成功或失败在本节追加，不提前声明单命令通过。

## 许可证据准备

新构建要求FSBL独立fsbl.map与应用ecg_runtime.map；sim/check_binary_licenses.py分别记录提取archive成员、实际库SHA、保留符号、编译器版本，区分LOAD/提取/最终section。已保留未改字节的GCC13.4.0 COPYING3/COPYING.RUNTIME和Newlib4.4.0.20231231 COPYING.NEWLIB，来源及SHA见docs/licenses/runtime_sources.json；原源码归档tmp，未安装或执行下载内容。受限执行的网络及ARM工具启动失败保留现象，正常授权工具上下文可下载/只读检查，未改系统权限。

上游许可材料不证明供应商二进制未打补丁，也不统一覆盖硬件IP。实际库及最终二进制结果待新构建完成后追加；最终模型、生成模板来源及适用AMD条款仍分开核对，不宣称最终法律/公开发布已完成。


## 最终完整重建与实际链接核对

原生单命令在tmp/c26正式清单副本中从头完成，输出tmp/c26/tmp/b/summary.json明确hardware_built_in_this_invocation=true、rate500、trace=false；初始无tmp，未引用其他历史工程/镜像，仍使用已有外部工具和原独立Python解释器。该次命令退出0并输出PASS FULL_REBUILD。早期c24/c25失败均保留，不把手动接续冒充本次从零。

新硬件建立/保持裕量0.329/0.057ns，布线DRC0，LUT1309/53200、寄存器1663/106400；这是沿用的原硬件，非新增CNN资源。bit4045773字节/SHA38987b8d96237f6c202ab235ee66a985d0faf6b643d19af26772d3cd380be452，XSA321427字节/SHA024ce170f05a28683e9593a2c69638b3c3aab47fa63156d3ee00d2150544394d。XSA内嵌bit与独立bit逐字节SHA相同，PS7/ECG参数与正式BD完全一致。

构建IDab3e1b7e7a4247c3，应用ELF454948字节/SHA9408c28641812ad198f34752643a00c8ff86dc0b5e8d9b167ea5b28321dbe509；FSBL358448字节/SHAc6825950092ddc7e64312a11e1c7e5caca5f44577385dc33dd1b4f4fe995387c。两份实际链接图268640/206119字节，均纳入build_manifest；所有导入源和当前正式文件SHA一致。现有压缩C格式等编译警告保留，未声称零警告。Windows PowerShell语法只读解析也通过。

sim/check_binary_licenses.py初次把链接图中缩进的依赖引用误认为实际库路径而失败，修复为只取未缩进的提取成员入口，失败目录binary_licenses保留，并增加提取/LOAD/丢弃section边界用例。最终证据binary_licenses_final/summary.json核对两份ELF、链接图、实际库SHA、成员、保留符号、GCC13.4.0和实际Newlib4.4.0头版本/SHA。

应用提取104个库成员，FSBL58个；libg只LOAD未单独提取、SHA与libc相同。FSBL保留7个md5/MD5符号，Eric Young声明确实适用于本候选；FatFs/RSA库未提取成员，不凭源码目录宣称已进入ELF。实际选中的生成BSP配置仍有无单独许可头的项，供应商工具链补丁对应、模板来源及适用IP分发条款继续待核；final_redistribution_cleared=false。完整原许可/来源表在docs/licenses.md及docs/licenses/runtime_sources.json，不把项目MIT扩展成全部二进制许可。

本轮仅完成当前候选构建/软件及虚拟传输边界，不是新实板、真实500Hz采集、无线、最终CNN或ARM/FPGA性能对比。旧latest未替换，Git/板卡/Flash未操作。


最终收尾：385份正式清单文件复制后的18组检查、135项测试全部通过，日志final_regression；实际扫描器新增版本头识别后再次对同一应用/FSBL执行通过。27项根README/资料索引/旧latest/模型协议快照SHA不变，冻结360Hz五份C数学/窗口来源SHA逐项不变，29份模型基线清单继续通过。新的负载/许可用例、许可原文及本轮记录已列入正式交接清单；tmp派生产物仍被既有ignore规则排除，无Git操作。
