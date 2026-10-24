# 主体离线准备与复现检查

## 目标与范围

2026-10-24用户要求将当前无需模型/ECG的工作完成后在system逐项勾选。本轮完成通信边界补强、500Hz合同整理、主机/通信计时入口、当前源码独立复现与依赖许可入口。整数算子只完成参考/RTL语法/独立综合；真实XSim数值仿真未成功，保留未勾选。

## 通信与记录

- RuntimeWorker增加maximum参数：默认64MiB、最小1024字节，超限失败并保留摘要；GUI沿用默认值，不改已有按钮行为。
- BridgeClient增加固定规模往返统计，I/READY、D/ACCEPTED、F/DONE及会话墙钟分别记录；不改变线上的报文字段或自动重传策略。
- 修正BridgeRecords.close：结果保存失败时摘要必须reason=failed，保留close_errors并释放源/结果句柄，不能留下completed成功标记。
- test_system_edges共14项（继承6项旧后台回归，新增8项），覆盖1024字节限额、4201样本/4096缓存与完整磁盘记录、缺口拒绝、写失败、运行中停止并排空前缀、收尾故障、阶段内存界及转换/容量界。假串口连接实际C核心，不是实物。

## 输入合同

新增docs/input_contract.md，对照当前解码器、转换器和C接收器；34字节/两通道、偏移码、CH2、500Hz软件时间轴与实际DRDY证据分开。旧500Hz/-1与新360Hz/4096严格区分，保留上游无源序号/未知丢样。test_input_contract两项直接核对当前C接收器：错误率/单位/ADC声明和跳号均拒绝，不接失败500Hz转换。修正bridge_protocol中蓝牙型号未知、从未上板两处过期陈述；原生500Hz最终合同仍受实采及算法暂停限制。

## 整数算子与失败

自编INT8多通道valid卷积、ReLU、最大池化参考与独立SystemVerilog实现，明确INT32最坏界、对称零点、右移中点远离零、饱和、布局、握手和复位；不支持最终模型尚未冻结的任意尺度/残差等算子。4项独立手算/边界通过。

独立Vivado2026.1对xc7z020clg400-2默认卷积参数综合通过，0错误/0警告，报告522 LUT、210寄存器、0 DSP/BRAM；仅该配置综合，不能代表最终CNN、实现、时序或板卡。证据tmp/system_finish_20261024/synth_01及synth.log。

check_int8_ops生成24组固定种子向量、8种SHIFT/ReLU配置、2688个卷积比较点和池化/复位断言；这些是待执行断言数量，不是通过成绩。xvlog语法分析通过，xelab默认MinGW6.2启动失败（Windows“无效的系统DLL重定位”）；关闭多线程、项目临时目录、8.3编译器和提升执行环境仍未成功。局部tmp工具视图/包装器仅尝试复用已有10.0编译器，没有改安装目录/权限；生成链接后XSim引擎以-1073741819退出，未见PASS，未采用此兼容尝试，也不把返回码0当通过。主要失败证据保留于int8_01..05、tool_view_attempt/shim/full_gcc等日志，未安装工具或修改系统配置。独立RTL数值验收仍阻塞。

## 计时与干净复现

sim/check_host_performance.py编译实际C并三次重放36000点受控脉冲，均124事件/124请求；QRS逻辑等待241样本。主机CPU QRS为2–4ms、完整pipeline为6–9ms，clock每秒1000tick，仅检查入口、不是精确性能结论。两条是重叠的独立回放，不相加或相减称切拍耗时；未测推理/PL字段null。PC往返包含传输与板端工作。详见docs/performance.md。

sim/check_system_offline.py从正式清单复制，不含历史tmp；使用当前已有Python3.14.7、GCC14.2、NumPy2.4.4/SciPy1.18.1/WFDB4.3.1/pandas3.0.6和Tk。第二轮13组检查（3静态检查及10测试模块）全通过；逐模块数量保留日志，继承用例不混称全新独立测试。旧latest17文件和模型基线29文件检查通过；68份保护文件SHA未变。复现仍使用已有外部依赖，不冒称全新电脑安装或最终硬件重建。许可/依赖范围见docs/dependencies.md，原第三方许可索引不改。

## 证据与未完成

[第二轮回归摘要](../../tmp/system_finish_20261024/regression_02/summary.json)、[主机计时](../../tmp/system_finish_20261024/perf_01/summary.json)、[保护文件核对](../../tmp/system_finish_20261024/protected_check.json)。工具临时视图是本机诊断产物，不复制给队友或作为正式依赖。

本轮没有新板测、训练、QRS数学改动、真实无线、最终模型、INT8分类精度或最终FPGA推理；未改根README/materials_review、旧发布或Git暂存区。仍缺XSim引擎可运行条件、真实采集/500Hz验收、最终模型/量化、ARM/FPGA最终对比及最终交付。教程和计划已同步。

最终收尾：344份正式文件复制到新的final_checkout；静态完整性、冻结QRS、旧release检查及14项边界重跑全通过。相对第二轮完整回归，代码仅有测试注释变动；68份保护文件仍完全一致，新说明相对链接检查无缺失。断点为tmp/system_finish_20261024/final_checkpoint.json，RTL仿真明确保持blocked。

后续更正：正常执行上下文中同一快照及未替换编译器的标准XSim流程均通过，原安装损坏归因证据不足。严格新覆盖通过和重建进展见[后续记录](system_build_20261024.md)，原失败保持原样。
