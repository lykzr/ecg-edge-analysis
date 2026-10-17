# ECG分类模型与训练准备核查（2026-10-16）

用户已要求开始模型训练，随后进一步要求多找现成、高质量模型。本次先盘点数据与依赖，再核对论文作者/维护者的模型代码、权重入口、许可、任务和部署边界；没有安装PyTorch、下载模型权重或启动训练。下表是来源核查和选型候选，不是本机复现成绩，不凭Star数量或README最高准确率判定质量。

## 当前数据和环境

当前Python3.14.7隔离环境有WFDB4.3.1/NumPy/SciPy，没有torch、torchvision或sklearn。系统CIM查询失败，未取得显卡/内存型号；PATH中未找到nvidia-smi，因此GPU能力仍未知，不能推断一定没有GPU。未改变全局环境。

新增[data/profile_classification.py](../../data/profile_classification.py)，读取当前42条原始记录，校验hea/dat/atr全部官方SHA256，统计原始心搏标签及候选切拍边界。QRS协议仅作为现有记录池清单，未沿用其开发/评估身份作为CNN划分。自有标注解析与WFDB官方rdann逐条比较，42条全部标注位置/类型一致。

| 候选研究分组 | 原始心搏数 | 暂定256点窗口完整数 | 含该组的记录数 |
| --- | ---: | ---: | ---: |
| N：N/L/R/j/e，包含束支和逸搏，不能等同健康人 | 86947 | 86909 | 42 |
| S：a/J/A/S，室上性异位相关 | 2546 | 2546 | 30 |
| V：V/E，室性相关 | 6601 | 6600 | 31 |
| F：F，融合搏动 | 801 | 800 | 16 |

另有Q（无法分类）15个，当前不强行并入N。合计96910个原始心搏标注；四组映射只是候选研究任务，尚未冻结类别/受试者集合、归一化或CNN验收指标。256点窗口为前96/后160点的初始盘点提案；若复用其他模型，必须按其采样率、窗口和预处理重新审查，不能默认直接喂入。类别映射核查依据[PhysioNet标注](https://archive.physionet.org/physiobank/annotations.shtml)。

盘点JSON和独立对照结果在tmp/cnn_prepare_20261016/data_audit.json、annotation_crosscheck.json，原始文本日志为[cnn_data_audit_20261016.log](cnn_data_audit_20261016.log)。

## 现成候选的核查结果

| 候选 | 可复用内容与证据 | 对本项目的判断 |
| --- | --- | --- |
| [CLEF-Small](https://github.com/Nokia-Bell-Labs/ecg-foundation-model) | 作者仓库称支持单导联表征；Small约448K参数，[Zenodo](https://zenodo.org/records/17572734)实际列出clef_small.ckpt约5.5MB；仓库BSD-3-Clause-Clear | 预训练迁移优先核查候选，不是现成N/S/V/F分类头；需查输入长度/重采样/预处理、骨干和适配成本。仓库已于2026-09-14归档只读，需承担维护；权重条款另核查，不将代码许可自动等同全部权重许可。 |
| [ECGFounder](https://github.com/PKUDigitalHealth/ECGFounder) | 作者提供预处理和微调代码，[官方模型页](https://huggingface.co/PKUDigitalHealth/ECGFounder/tree/main)列1导联及12导联权重，各约370MB，模型页标MIT | 有实际预训练权重与单导联版本，适合作为PC迁移/对照候选。输出任务与我们的心拍四组不同；规模较大，不作为7020首个直接部署目标。 |
| [ECG-FM](https://github.com/bowang-lab/ECG-FM) | 作者提供权重、教程与配置，约90.9M参数；仓库MIT | 有论文/公开权重支持的通用表征模型，优先PC侧研究。既有长片段/多导联任务不能直接替换本项目的单心拍分类接口。 |
| [torch_ecg](https://github.com/DeepPSP/torch_ecg) | ECG专用PyTorch框架，MIT；含MITDB读取、ResNet等已实现骨干和训练/评价组件 | 适合复用成熟代码训练任务匹配的基线，不等于附带本项目可直接使用的心拍权重。其ROADMAP列有未完成模型，不能因目录存在就认为实现可用。 |
| [Tiny MF-CNN论文](https://doi.org/10.3390/s23031365) | 作者研究MIT-BIH跨受试者分类、量化及边缘运行，模型变体约1267—1619参数；含RR输入 | 从规模看是轻量部署候选，但本轮未找到作者官方权重。论文较好结果对应特定三类变体，不能直接套成四/五类结果；包含后RR，在线输出需等待后续心搏。第三方复现另行核查许可与来源。 |
| [PTB-XL官方基准](https://github.com/helme/ecg_ptbxl_benchmarking) | 论文作者提供训练模型、预测及微调示例；划分训练fold1—8/验证9/测试10；GPL-3.0 | 可参考严谨评估/ResNet、Inception等实现，但十二导联记录级任务与本项目不同，需适配；不能将其代码直接重标MIT。 |
| [Mousavi作者seq2seq](https://github.com/MousaviSajad/ECG-Heartbeat-Classification-seq2seq-model) | 有论文作者代码和跨/同受试者入口，存在TF2目录；README仍列Python2.7，许可说明限学术非商业 | 研究对照可看，兼容和部署成本高，不作为首个7020路线；不能按MIT/Apache组件直接并入。 |
| [TenzinDhonyoe单心拍分类器](https://github.com/TenzinDhonyoe/ecg-arrhythmia-mitbih-pvc-pac-classifier) | MIT，仓库称提供MLII/360Hz、ResNet权重、模型卡和记录级划分 | 工程接口/公开失败有参考价值，但其三类ResNet自报macro-F1约0.586，五类已发布表中的主成绩是LR基线，不能把“五类支持”当高性能五类CNN已验证。没有本机运行确认。 |
| [ECG FPGA SE案例](https://github.com/niteshg97/ecg-fpga-se-networks) | MIT，仓库给权重加载入口和hls4ml流程，目标xc7z020clg400-1 | ECG5000二分类、约1674参数；当前架构主体是逐时刻Dense/SE，并非目标四类1D-CNN。自报综合DSP210/220、24位定点，不能写成已完成INT8或本板实测；仅作为工具链/数值问题参考。 |
| [Ishaq-ML FPGA CNN案例](https://github.com/Ishaq-ML/ecg-cnn-fpga-deployment) | MIT，声称6868参数的搜索CNN、TFLite INT8和COE导出；硬件说明目标Virtex-6 ML605 | 类别是N/A/束支/V，和N/S/V/F不同；硬件章节又采用16位Q8.8，与软件INT8不等价。未核查其完整代码/训练划分和硬件日志，不能把README成绩当作可信可直接复用的本项目结果。 |

以上仅核查网页/仓库说明、论文相关内容和权重文件清单，未逐行审查所有代码、下载/校验权重或完成推理。部分页面获取失败时使用作者其他公开入口定位，不据此宣称失效文件已经验证。

## 下一步建议

优先核查CLEF-Small的实际骨干、输入合同、权重许可及最小推理，再判断能否微调到单心拍；同时把MIT许可的torch_ecg已实现小骨干或论文轻量结构作为任务匹配基线。预训练不保证在本数据上更好，必须用同一分类协议比较。Tiny MF-CNN不能宣称有作者现成权重；大基础模型不因论文知名就默认适合7020。

正式训练前另冻结受试者划分、标签、预处理和分类头，检查现成权重训练数据是否包含计划测试记录；有重叠时不能宣称独立泛化。现有42条都用于过QRS算法研究，分类器评估与整条系统独立性需分别说明。还要给参数/MAC/激活缓存预算，预训练checkpoint大小不等于FPGA资源消耗；量化需独立验证。

本轮未选择最终模型、未安装训练依赖、未改QRS/RTL/PS或发布镜像、未运行Git；smoke仍未上板测试。日志统一写docs/records，未往README写实验成绩。
