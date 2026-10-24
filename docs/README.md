# 工程文档导航



按信息采集、项目主体、模型训练查找文档。[总计划](../report/project_plan.md)统一维护目标与排期；[修改日志](records/lykzr.md)按相同三类记录过程。



三份计划使用短文件名：capture.md（采集）、system.md（主体）、model.md（模型）。标准入口README.md、AGENTS.md保持原名；其他已有教程和历史报告本轮不改名。



## 信息采集



| 文档 | 用途 |

| --- | --- |

| [信息采集计划](../report/capture.md) | 前端/ADC、采样、滤波与采集输出接口 |

| [资料索引](materials_review.md) | 板卡手册及资料入口 |

| [ADS1292R资料与解码](ads1292.md) | 模块图/例程冲突、两版帧格式、24位离线解码及接入待核项 |



## 项目主体

[QRS逐样本运行时与切拍](qrs_runtime.md)：独立软件参考、输入幅值/序号、500Hz适配与模型窗口接口；实际检查见[运行时记录](records/runtime_20261023.md)。



| 文档 | 用途 |

| --- | --- |

| [项目总体控制计划](project_control_plan.md) | **面向总体负责人**：决策树、应急方案、时间表和协作机制 |

| [下载与串口教程](download_guide.md) | Vivado/Vitis、JTAG、QSPI和smoke操作 |

| [smoke自检与交接](smoke_handoff.md) | 统一使用入口，内含当前交付、板上证据及交接/发布记录链接 |

| [项目主体计划](../report/system.md) | 检测/切拍、FPGA部署、电脑通信显示与整机交付 |

| [历史交接完整性审查](records/checkout_20261017.md) | 2026-10-17依赖与复核记录；当前操作以现有说明和检查脚本为准 |


| [Zynq到电脑的结果协议](uart_protocol.md) | ECG-UART-1输出字段/能力/缺失值；电脑输入另见ECG-IN-1 |

| [电脑送样协议](bridge_protocol.md) | 分段路线、ECG-IN-1输入/确认与结果协议边界 |

| [电脑双向中转](bridge.md) | 厂商/CSV入口、USB_UART收发、独立PS接收应用及离线检查 |

| [PS流式应用](ps_stream.md) | 独立合成流工作区、构建/运行、发送队列与故障边界 |

| [500Hz合成流上板记录](records/stream_board_20261020.md) | 用户完成的有限合成送样与PC保存核验；不代替双向中转 |

| [双向数字回放与计时修复](records/bridge_board_20261020.md) | 计时宏故障、修复版ELF、CSV/脉冲实板收发及保留的算法缺口 |

| [PC波形监视器](pc_monitor.md) | 演示/结果、USB身份识别、CSV/蓝牙与中转界面；有限数字回放已上板，真实无线/人工界面待验 |

| [电脑UI源码入口](../src/ui/README.md) | src/ui/main.py启动，三个窗口与共享绘图；通信/数据后台在src/pc |

| [寄存器接口](register_map.md) | PS/PL寄存器和事件接口 |

| [工程实验记录](records/lykzr.md) | 按相同三类记录问题、失败、取舍和验证证据 |


| [QRS离线评估](records/offline_qrs_evaluation.md) | 检测方法、记录划分和准确性评估 |

| [Hello World验证](records/hello_world_validation.md) | 发布镜像验证证据 |


| [历史说明](records/readme_history.md) | 从各README迁出的原始说明/记录 |

| [启动与早期离线历史](records/bringup_history.md) | 从下载教程迁出的启动排错和实验结果 |





系统两轮：输入幅值与持续数字验收集中记录零事件原因、冻结门槛、持续用例及剩余边界。



系统JTAG发布与归档记录说明当前latest、旧版history、精确忽略规则及便携检查。



[启动学习与候选峰修复](qrs_auto.md)说明独立候选的预热、码域、构建和已验发布隔离；实际结果见[修复记录](records/qrs_auto_20261021.md)。

[原波形定位与质量确认](qrs_peak.md)是独立QRS软件候选；失败分支和未通过门槛见[记录](records/qrs_peak_20261021.md)，不属于当前板端镜像。

QRS一次定时接续保留后续噪声假设、成熟对照与运行时边界。

QRS第二轮修复记录保留形态/宽度/双流定位取舍和未验边界。

[成熟QRS接续候选](qrs_v5.md)提供独立v5的输入约定与完整回归入口；试验取舍和未验边界见[接续记录](records/qrs_continue_20261021.md)。

[研究26复测与采用结果](records/qrs_research26_20261023.md)：2026-10-23 完整42条已知开发回归 41/42，105 噪声误检未过；数据SHA未变，不称独立测试。

[评估修正与三天计划](../report/project_plan.md#评估修正与三天工作安排)列明检索依据、停止规则与噪声实验优先级；[研究快照复现](qrs_research.md)和[DS隔离任务](ds_task.md)用于安全交接。

## 模型训练



| 文档 | 用途 |

| --- | --- |

| [CNN问题分析与改进建议](cnn_analysis_and_suggestions.md) | **面向模型负责人**：诊断框架、改进方案、决策时间表 |

| [模型训练计划](../report/model.md) | 数据/基线对照、训练验证、独立测试、量化和模型交付 |

| [CNN资产迁移记录](records/model_structure_20261023.md) | 2026-10-23 CNN协议/准备/训练/基线迁入 model/，路径与检查同步 |

| [心拍分类与疾病范围记录](records/ecg_scope_20261017.md) | 保存任务范围与解释边界；历史状态不代表当前验收 |

| [轻量CNN首版说明](cnn_baseline.md) | 固定模板基线的冻结协议和实现边界 |

| [可训练CNN说明](cnn_trainable.md) | PyTorch候选、训练/验证选型和复现入口 |

| [扩库CNN说明](cnn_expanded.md) | INCART患者划分、SVDB辅助训练及独立测试开封流程 |

| [患者CV与来源对比](cnn_patient_cv.md) | 开发患者三折、辅助来源对比、时序CNN及独立复核 |

| [目标来源微调与比例校正](cnn_target_adapt.md) | 同折权重适配、患者均衡损失与误报/召回取舍 |

| [因果历史形态背景CNN](cnn_background.md) | 标签无关历史窗口、配对训练、前缀与完整权重检查 |

| [CLEF-Small备选](model_candidates/clef_small.md) | 暂缓的预训练迁移路线及恢复条件 |








| [模型训练交接](model_training_handoff.md) | 克隆后获取数据、重建输入与复现训练 |



README只放工程说明和文档入口；实验、失败、实际输出和性能/准确率记录留docs/records/，原始数据、CSV、缓存和备份放tmp/。只按任务验收条件勾选计划，历史记录不当作当前完成状态。



Git记录范围：docs/records/保留报告和过程说明；原始下载、安装、逐轮训练及重复检查.log保留本地，默认不跟踪。仅.gitignore逐文件列出的精选日志随仓库；其他历史日志链接可能仅作者本机可用，不批量放行。教程内容和发布文件不随导航分类修改。



QRS受控噪声入口：[使用说明](qrs_noise.md)，[实验记录](records/qrs_noise_20261023.md)。

分类集成：[分类接口](classification_protocol.md)定义128点、训练折RR、身份/有效状态、有界队列与E单发；[接口验证记录](records/classification_20261023.md)保存软件闭环、失败和PS移植边界。

冻结360Hz新流程：[ARM运行与标准CSV入口](runtime_board.md)，[移植/实板记录](records/system_port_20261024.md)。厂商500Hz旧入口和真实无线仍单独验收，不把两种合同混用。

主体准备入口：[输入合同](input_contract.md)、[整数算子](int8_ops.md)、[性能测量](performance.md)。

当前源码复现及许可边界见[依赖与许可](dependencies.md)。

主体离线准备及XSim阻塞证据见[本轮记录](records/system_offline_20261024.md)。

后续主体入口：[当前设计开发稿](../report/design.md)、[裸机许可复核](licenses.md)。

标准仿真复核、重建与故障状态的后续证据见[主体后续记录](records/system_build_20261024.md)。

## 500Hz源输入

500Hz ARM适配、源切拍与独立标准CSV入口见[500Hz处理](rate500.md)；配对实验及失败见[500Hz记录](records/rate500_20261024.md)。
