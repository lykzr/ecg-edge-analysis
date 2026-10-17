# 工程文档导航

| 文档 | 用途 |
| --- | --- |
| [下载与串口教程](download_guide.md) | Vivado/Vitis、JTAG、QSPI和smoke操作 |
| [跨电脑smoke交接](smoke_handoff.md) | 独立工程包、接收方工作区生成与JTAG自检 |
| [工程计划](../report/project_plan.md) | 目标、优先级、缺项和验收条件 |
| [HDMI 显示方案](HDMI.md) | 外接显示器的硬件依据、集成方案、与 smoke 的关系、验收与排期 |
| [PC ↔ Zynq UART 协议规划](uart_protocol.md) | USB-UART 双向通信的数据清单、帧格式、板端/PC 端实现、历史记录与待定项 |
| [心拍、节律与疾病范围记录](records/ecg_scope_20261017.md) | 四分类覆盖、ADS1292R能力及异常提示的解释边界 |
| [轻量CNN首版说明](cnn_baseline.md) | 固定模板基线的冻结协议和实现边界 |
| [可训练CNN说明](cnn_trainable.md) | PyTorch候选、训练/验证选型和复现入口 |
| [扩库CNN说明](cnn_expanded.md) | INCART患者划分、SVDB辅助训练及独立测试开封流程 |
| [患者CV与来源对比](cnn_patient_cv.md) | 开发患者三折、辅助来源对比、时序CNN及独立复核 |
| [目标来源微调与比例校正](cnn_target_adapt.md) | 同折权重适配、患者均衡损失与误报/召回取舍 |
| [因果历史形态背景CNN](cnn_background.md) | 标签无关历史窗口、配对训练、前缀与完整权重检查 |
| [CLEF-Small备选](model_candidates/clef_small.md) | 暂缓的预训练迁移路线及恢复条件 |
| [寄存器接口](register_map.md) | PS/PL寄存器和事件接口 |
| [资料索引](materials_review.md) | 板卡手册及资料入口 |
| [工程实验记录](records/lykzr.md) | 按任务记录问题、取舍和验证证据 |
| [拆分后准确性复核](records/qrs_recheck_20261016.md) | 文件整理后的全记录复现结果 |
| [QRS离线评估](records/offline_qrs_evaluation.md) | 检测方法、记录划分和准确性评估 |
| [CNN模型选型与准备](records/cnn_model_survey_20261016.md) | 现成模型、权重、许可及数据盘点 |
| [固定模板CNN首轮记录](records/cnn_mf_v1_20261017.md) | 训练结果、逐类失败及后续验证边界 |
| [可训练CNN尝试记录](records/cnn_trainable_20261017.md) | 多结构、增强、上下文实验及验收结果 |
| [扩库与新患者验证记录](records/cnn_expansion_20261017.md) | S/F来源盘点、患者划分、重训与测试保留状态 |
| [患者CV与来源对比记录](records/cnn_patient_cv_20261017.md) | 12次训练、逐类/逐患者结果、权重重放与失败结论 |
| [目标微调与比例校正记录](records/cnn_target_adapt_20261017.md) | 六次微调、九方案取舍、完整权重重放及未达标结论 |
| [历史形态背景记录](records/cnn_background_20261017.md) | 完整背景重建、九次训练、冻结支路对照与无收益结论 |
| [Hello World验证](records/hello_world_validation.md) | 发布镜像验证证据 |
| [工程状态快照](records/project_status_snapshot.md) | 既有实验阶段与证据摘要 |
| [历史说明](records/readme_history.md) | 从各README迁出的原始说明/记录 |
| [启动与早期离线历史](records/bringup_history.md) | 从下载教程迁出的启动排错和实验结果 |
| [本轮文档维护](records/doc_maintenance_20261016.md) | 整理范围、修改、验证和后续维护入口 |

README仅保存项目用途、目录、依赖、接口、构建/运行步骤和文档链接。日期流水、失败尝试、实际输出、性能/准确率成绩及实验分析统一写docs/records/。原始数据、CSV、工具工作区、缓存和备份放tmp/，正式记录链接对应证据。需要长期保留的新验证文本日志也写docs/records/，不放回README。

模型训练接手从[训练交接](model_training_handoff.md)开始；旧实验的归档路径与工程复核见[本次整理记录](records/structure_handoff_20261017.md)。

当前[Git训练交接](model_training_handoff.md)提供克隆后的数据获取/训练步骤；[smoke板上通过记录](records/smoke_board_validation_20261017.md)保存用户返回的原始UART与报告。

[当前smoke交付](../releases/latest/README.md)与[发布归档/核查记录](records/smoke_release_20261017.md)分别保存使用入口和实际验收过程。

Git记录范围：docs/records/保留报告和过程说明；原始下载、安装、逐轮训练及重复检查.log仍保留本地，默认不跟踪。仅.gitignore逐文件列出的smoke原始UART/启动、发布核验、QRS复核和当前CNN权重复核日志随仓库；旧报告中的其余日志链接可能只在作者本机可用，可按正式脚本复现，不批量放行所有.log。
