# DS隔离任务：受控噪声实验准备

请把本文件完整交给DS，不需要它知道旧对话。项目是Zynq-7020心电边缘分析；当前QRS检测存在噪声误检，CNN另由他人负责。当前最好研究快照仅已知42条中41条过门槛，未整体合格，不是板端实现。

## 工作位置与硬边界

在解压/生成的ds_noise目录工作。先读该目录AGENTS.md。input/project/是项目只读副本，input/raw/若存在数据则是118、119的已知开发副本（生成时可不带原始数据）；只能修改work/、output/、logs/。不要打开或修改原工程，不使用Git、Computer Use、板卡/串口，不安装、下载、训练模型或启动旧实验。Python运行加-B；缺NumPy/SciPy/WFDB则只做标准库检查和缺项报告，不安装。每次运行开始/结束都用check_inputs.py核对input目录SHA；核对失败立即停止并报告，不自己恢复。

用户本轮明确要求DS隔离，因此本任务日志写到本隔离目录logs/output，正式docs/records和项目计划由Codex审核后同步。此范围优先于要求向正式工程追加日志的一般规则。不得修改任何AGENTS、许可、检查脚本、输入清单或input文件。

## 先读这几份材料

input/project/report/project_plan.md、docs/qrs_research.md、data/qrs_research_protocol.json、data/qrs_v5_protocol.json、data/ecg_dataset.py、data/benchmark_qrs_v4.py、data/benchmark_qrs_research.py，以及src/reference/qrs_research/provenance.json。说明：前者可从原码重建研究26，仍是离线重放，不是完整在线运行时；不得沿用“有界”字符串把所有诊断状态称为有界。

## 只做以下交付，不自行改算法

1. 在output/inventory.json列出现有输入、字节数、SHA256、采样率、通道、标注路径；缺项写missing，不补造。原42条已查看，118/119加噪衍生也只是开发压力数据。
2. 在output/noise_protocol_draft.json列官方NST的118e24/18/12/06/00/_6、119同组和两个干净参考，共14项（注意实际官方文件名118e06、118e_6）。噪声为电极移动em，预定SNR为24/18/12/6/0/-6dB。每个噪声记录必需.hea/.dat/.atr与官方SHA；列官方网址、所缺文件。不要调用下载、不要联网获取数据。若已有完整NST也不自行打开未列数据。
3. 在work/编写一个小脚本，必须显式接收--raw-dir、--output-dir；拒绝输出到input或目录外、拒绝覆盖已有输出。不启动长评估。先用合成小数组做校准/长度/错峰/丢拍/误拍计分的自检；不得用合成成绩声称真实抗噪提高。若只用RMS信号/噪声比，名称必须是RMS_SNR，明确不等同官方NST校准。
4. 提交output/report.md：实做、命令、通过/失败的自检、缺项、与正式算法的关系。README只写用途、依赖、运行方法，实验结果写report.md。输出任何实验结论都须有完整命令和输出文件，不写“准确率达标”。
5. 结束再次check_inputs.py通过后，最后才写output/DONE.json，包含status=ready_for_review或blocked、输入清单摘要、交付文件列表、待办。完成这个小任务就停止，不帮忙整理原工程、不修改计分门槛、不跑42条或CNN、不打开保留6人。

原门槛仍为每记录Se/PPV/V召回>=99%、位置MAE<=10ms、RR<=15ms；专家标注只用于离线计分，运行时不能借标签定位。不要按患者ID设特例，不删噪声/难拍，不把不同候选最佳成绩拼起来。任务是准备可审核实验入口，不要求你把检测器改到合格。

## 给DS的可直接粘贴开场

“只在我提供的ds_noise隔离目录完成本说明的5项交付。先读AGENTS和任务说明，列出准确写入路径，再写代码。input只读，写入限work/output/logs；运行前后校验SHA。缺数据/依赖就报告blocked，不安装、不下载、不改原工程。完成小自检后写DONE.json并停止。”
