# 第三方来源与许可边界

根 LICENSE 的 MIT 许可用于本项目贡献者有权授权的自有代码和文档，不替代第三方原有许可。后续引入新组件时保留其版权和许可，并在本文件追加来源。

| 内容 | 来源与处理 |
| --- | --- |
| MIT-BIH波形和标注（当前范围42条，名单见data/qrs_v4_protocol.json） | [PhysioNet MIT-BIH 1.0.0](https://physionet.org/content/mitdb/1.0.0/)，本库提供获取脚本与引用；原始文件留在 tmp/，不作为自有代码改标MIT。数据使用条件以该版本官方页面及原许可为准。 |
| INCART波形与标注 | [St Petersburg INCART 1.0.0](https://physionet.org/content/incartdb/1.0.0/)，DOI:10.13026/C2V88N，ODC Attribution v1.0。官方患者映射随原始资料保留，使用II导联；类别人工修正不等于位置人工修正。原始文件只放tmp，固定版本SHA256校验，不重新授权为项目MIT。引用数据库及PhysioNet原平台论文。 |
| SVDB波形与标注 | [MIT-BIH Supraventricular Arrhythmia Database 1.0.0](https://physionet.org/content/svdb/1.0.0/)，DOI:10.13026/C2V30W，ODC Attribution v1.0。仅辅助训练，ECG1导联位置及患者身份未确认，不声称78个独立患者；保留数据库和PhysioNet引用。原始数据不改标MIT。 |
| LTDB长程辅助波形与标注 | [MIT-BIH Long-Term ECG Database 1.0.0](https://physionet.org/content/ltdb/1.0.0/)，George Moody，DOI:10.13026/C2KS3F，ODC Attribution v1.0。人工复核心拍标注，仅辅助训练；导联解剖位置及患者映射未确认，原始gain0不当已知标定。数据与元数据留tmp，不改标MIT。 |
| 欧洲ST-T候选元数据 | [European ST-T Database 1.0.0](https://physionet.org/content/edb/1.0.0/)，DOI:10.13026/C2D59Z，ODC Attribution v1.0。当前只获取校验清单、头文件和标注以盘点S/F，不加入训练。原论文：Taddei等，European Heart Journal 13:1164–1172,1992。 |
| 双二阶滤波公式及WFDB标注定义 | 滤波系数按[W3C Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/)数学公式独立实现；心搏/非心搏类别依据[WFDB官方说明](https://physionet.org/physiotools/wpg/wpg_36.htm)及其ecgcodes.h数值定义。该滤波参考为自有实现；v3/v4另有下述WFDB依赖及衍生代码。 |
| WFDB-Python 4.3.1 / GQRS / XQRS | [固定版本源码](https://github.com/MIT-LCP/wfdb-python/blob/v4.3.1/wfdb/processing/qrs.py)，MIT许可。XQRS、原版GQRS作为离线对照；流式候选继承GQRS并使用由其决策循环派生的[src/third_party/gqrs_core.py](src/third_party/gqrs_core.py)。完整版权和MIT许可保存在[src/third_party/wfdb_license.txt](src/third_party/wfdb_license.txt)，来源/转换/哈希保存在[gqrs_provenance.json](src/third_party/gqrs_provenance.json)，生成器为[extract_gqrs_core.py](build/extract_gqrs_core.py)。依赖WFDB原类，不是无依赖独立移植。官方文档说明GQRS不再积极开发/支持；本项目的流式改造与维护责任属于本项目，不宣称得到上游验证。 |
| NumPy、SciPy、pandas与matplotlib等Python依赖 | v3/v4使用隔离环境安装WFDB及其依赖，版本记录在计分摘要environment中；各自许可保留，未复制安装包到正式源码。data/requirements_qrs.txt固定WFDB版本，不等于全部传递依赖的锁定文件。 |
| v2窄带、斜率平方与近邻斜率判断思路 | 参考Pan J, Tompkins WJ. A Real-Time QRS Detection Algorithm. IEEE TBME 32(3):230–236, 1985，DOI:10.1109/TBME.1985.325532。[论文副本](https://people.ece.cornell.edu/land/courses/ece5030/labs/s2013/Pan_Tompkins.pdf)。本项目独立编写原型，未复制第三方实现源码，也不是论文全部规则/系数的完整复现；论文准确率不作为本库结果。 |
| MF-CNN公开结构 | Farag MM. [A Tiny Matched Filter-Based CNN for Inter-Patient ECG Classification and Arrhythmia Detection at the Edge](https://doi.org/10.3390/s23031365), Sensors 2023, 23, 1365，论文CC BY 4.0。本项目依据固定模板卷积/共享RR分支/分类头思路独立编写NumPy改编实现，未复制第三方源码、图表或权重；差异见[工程说明](docs/cnn_baseline.md)，不能套用论文结果。自有实现的许可不改变论文或其他资产的许可。 |
| 可训练轻量CNN与残差结构 | MF变体继续参考Farag 2023；残差心拍结构思路参考Kachuee等[ECG Heartbeat Classification: A Deep Transferable Representation](https://arxiv.org/abs/1805.00794)，未复制其源码、权重、图表或论文正文。自有PyTorch改编的结构、输入、RR、归一化与论文不同，不能继承论文成绩或把原资料改标MIT；具体差异见[说明](docs/cnn_trainable.md)。 |
| PyTorch CPU训练依赖 | 使用[官方CPU轮子](https://download.pytorch.org/whl/cpu)安装到项目tmp独立环境，版本与依赖清单保留在实验目录。PyTorch采用原有BSD风格许可并含第三方依赖，安装目录保留原许可证；不把训练框架或其依赖重新授权为项目MIT，不复制整个环境到发布目录。 |
| AMD BSP、FSBL、IP及工具生成内容 | 使用Vivado/Vitis 2026.1生成，相关代码/库保留AMD及其依赖的原许可。releases/latest中的二进制不意味着其中所有组成部分重新授权为MIT；正式对外发布前补查对应源码/许可交付要求。 |
| 正点原子原理图、手册与官方工程 | 原始资料只读参考，未作为本项目自有源码重新授权。不要将下载盘或手册自动上传到仓库。 |
| 竞赛指南及参考PDF | docs/reference/为本地参考，忽略共享；未确认公开再分发权限。 |
| Python、matplotlib、Vivado/Vitis | 外部运行/构建工具，按各自许可独立使用，本库不复制其安装目录。 |

数据库引用：Moody G, Mark R. MIT-BIH Arrhythmia Database, version 1.0.0. PhysioNet. DOI:10.13026/C2F305。原论文：Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Engineering in Medicine and Biology 20(3):45–50, 2001。

新增数据库按各行题名、版本、作者/贡献机构、DOI及[ODC Attribution v1.0](https://opendatacommons.org/licenses/by/1-0/)归属引用。INCART贡献者为St. Petersburg Institute of Cardiological Technics，官方页面列出Tihonenko、Khaustov等；PhysioNet当前标准平台引用为Pollard等，PhysioNet as a global platform for biomedical research，Nature Health 2026，DOI:10.1038/s44360-026-00096-z。元数据和派生缓存不意味着已对外发布原数据库。

自有实现未因参考资料而取得第三方资产的版权。当前仍是开发仓库，完整第三方组件和最终发布包许可审查列入计划，尚未声称已全部完成。

`src/reference/ecg_temporal_cnn.py`为项目自有两层Conv1D与分段池化/RR分支实现，使用PyTorch通用算子，无新增第三方源码或预训练权重，不声称是某个官方预训练模型。既有残差对照的结构来源保持上表；比较设计见[患者CV说明](docs/cnn_patient_cv.md)，开发验证成绩不能继承论文成绩。
