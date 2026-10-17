# 2026-10-17 结构整理与模型训练交接

## 目标和实际变动

用户准备把模型训练交给另一位成员，要求将目前不用的内容放tmp。本轮不训练，不安装，不操作Git、板卡或Flash。

按导入关系检查当前v8训练、缓存准备和验证流程，保留其必要公共依赖的原字节：train_cnn_candidates.py、train_cnn_refined.py、ecg_mf_cnn.py虽然名字对应旧尝试，仍分别提供计分/训练工具、网络构建/增强及指标。没有为目录整齐而把当前依赖搬入历史，也没有修改冻结源码或协议哈希。

归档位置：`tmp/history/training_handoff_20261017/`。32个移动入口，共293个文件、43,857,578字节，逐文件SHA256在移动前后相同。包括独立v1/v4/v6旧训练入口与旧协议、v9—v11专用实现和测试、两份旧AC7020名称兼容Tcl入口，以及根目录旧vivado、_ide、.rigel_lopper、.Xil、torchinductor缓存。两份AC7020入口原本是转发领航者脚本的兼容包装，不是本轮删除了另一套有效板级实现。

归档前用Win32_Process检查，没有发现Vivado/Vitis/Python/Java/loader/hw_server活动进程；逐路径确认在本项目内且无目标覆盖。旧工具工程保留原内容，未批量改XPR内部路径；回用前需在副本核对路径或正式重建。旧路径及恢复位置见归档manifest.json，不在归档目录直接执行历史脚本。

现有tmp原始数据、开发缓存、训练环境、权重和全部失败运行未移动，tmp/ecg_smoke与QSPI工作区未动。文字实验记录留docs/records；只修正其中指向已迁移文件的Markdown链接，不改旧成绩、协议或来源正文。

工程说明更新data/README、sim/README、build/README、docs导航和计划；历史教程标注已归档，当前统一入口为[训练交接](../model_training_handoff.md)。本机旧bit路径同步更新myself.md。根README、docs/materials_review、HDMI文档及releases/latest未修改。写前文档副本保留tmp/backup/training_handoff_20261017/。

## 实际验证

- 数据环境Python3.14.7：当前sim软件测试44项，34通过、10项因缺Torch跳过；日志[training_handoff_data_tests_20261017.log](training_handoff_data_tests_20261017.log)。
- CPU Torch2.14.1环境：当前sim软件测试34项，22通过、12项因缺WFDB等跳过；日志[training_handoff_torch_tests_20261017.log](training_handoff_torch_tests_20261017.log)。跳过不算通过，两套环境覆盖不同依赖。
- 完整重放v8四候选×三折共575,664个开发验证预测，逐拍、逐类、逐患者、数据/权重/当前源码/运行快照哈希、RR来源、门槛及选型全部核对一致。证据tmp/training_handoff_cv_verification_20261017.json与[重放日志](training_handoff_cv_verification_20261017.log)。本轮没有重新训练，原336轮仅为旧运行轮数，不是本轮新增训练。
- 整理不改变分类质量：三折平均macro-F1为0.641363、合并OOF为0.623916，S/F仍不合格。该检查是既有开发数据重现，不是新的独立测试。

## 交接内容与限制

打包入口data/package_training_handoff.py，将当前工程文本、约108MB压缩开发缓存、完整v8对照结果、归档的旧专用源码/协议及逐文件哈希打成ZIP；不包含旧工具工作区、虚拟环境、原始数据库、独立测试缓存和板卡镜像。包不是完整原始数据重建环境，也不是板卡交付物；接收方先校验文件、重放旧权重，再在新协议/输出中实验。数据库来源与许可保留third_party.md。

独立6名INCART患者未评估；没有全开发最终拟合、INT8、PL推理或自动切拍验收；smoke仍未上板测试。模型负责人待用户和队友确认。本轮只生成本地交接物，不发送、上传或发布。

## 最终检查补充

归档293文件和保留67项源码/协议/发布文件哈希复核一致；37份当前Python语法通过，AST导入检查未发现正式代码导入已归档模块。证据tmp/training_handoff_structure_verification_20261017.json。

完整文档检查44份Markdown、306条链接；受保护README/资料索引/latest及11项QRS冻结哈希通过。全库仍有4条缺失文件链接：docs/README.md一处、docs/uart_protocol.md三处指向HDMI.md。当前HDMI.md已不存在，新uart_protocol.md来自其他工作，本轮未移动或恢复它们；保留并发内容，不能据旧备份恢复他人文档，也不能称全库链接通过。日志见training_handoff_doc_check_20261017.log，快照tmp/training_handoff_doc_verification_20261017.json。本轮新增交接/归档链接均可定位。

初版交接包01共345文件（另含内部清单），已实际解压至tmp/handoff/received_check_20261017_01，全部文件哈希通过；使用解压后的验证器、数据和权重再次完整重放12组575664条验证预测，结果一致。日志training_handoff_portable_replay_20261017.log。它验证同机改路径可运行，不能代替接收方真实电脑验收，也没有在第二台机器安装依赖。

最终供拷贝版本为tmp/handoff/ecg_training_handoff_20261017_02.zip及同名.sha256，补入本次交接说明与上述实际结果。最终ZIP的字节数、SHA256、逐文件校验及与当前源文件对照见tmp/handoff/final_package_verification_20261017.json；01作为本地打包验证历史留tmp，不是需同时交付的第二个版本。

