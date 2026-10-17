# 通过Git交接模型训练

本项目按Git仓库交接：队友克隆源码后，从官方固定版本下载数据，在自己的tmp目录生成缓存和环境，再运行训练。不依赖本机ZIP、虚拟环境、父缓存或历史归档。原先ZIP路线仅为本地历史，不是当前交接要求。

## 队友从这里开始

以下为Windows PowerShell命令。从Git仓库克隆；如果集成人还没提交推送本轮文件，远端克隆不会自动包含这些改动。先确认集成人给出的提交号，再开始，不以本地文件存在冒充已共享。

```powershell
git clone https://github.com/lykzr/ecg-edge-analysis.git
Set-Location ecg-edge-analysis
# 仅需标准Python：先确认工作副本包含全部交接入口。
python -B sim/check_training_checkout.py
# 接收方在获准的项目独立环境安装；不改系统Python或驱动。
python -m venv tmp/cnn_data_env
& './tmp/cnn_data_env/Scripts/python.exe' -m pip install -r data/requirements_cnn_data.txt
python -m venv tmp/cnn_torch_env
& './tmp/cnn_torch_env/Scripts/python.exe' -m pip install -r data/requirements_cnn.txt
# 只下载协议中的61条INCART开发记录及42条MIT已知开发记录；校验冻结SHA。
& './tmp/cnn_data_env/Scripts/python.exe' -B data/prepare_cnn_git.py download --raw-dir tmp/cnn_git/raw
& './tmp/cnn_data_env/Scripts/python.exe' -B data/prepare_cnn_git.py prepare --raw-dir tmp/cnn_git/raw --output-dir tmp/cnn_git/cache
# 当前仅复现已选residual_verified，按冻结患者三折训练；不是v8的全部4候选。
& './tmp/cnn_torch_env/Scripts/python.exe' -B data/train_cnn_cv.py --cache-dir tmp/cnn_git/cache --protocol data/cnn_git_v1_protocol.json --output-dir tmp/cnn_git/run_01
& './tmp/cnn_torch_env/Scripts/python.exe' -B sim/verify_cnn_cv.py --cache-dir tmp/cnn_git/cache --run-dir tmp/cnn_git/run_01 --output tmp/cnn_git/run_01_verify.json --replay-weights
```

输出目录必须不存在；错误/中断缓存保留，用新目录重试。下载脚本校验已有文件，可继续未完成下载，但不覆盖错误字节。原始数据、环境、权重和预测留tmp，不通过Git提交。网络下载、环境安装受接收方授权与网络条件约束；本机已完成原始数据重建，未在第二台电脑安装运行，不承诺训练时长或跨框架位级一致。

## 协议、代码和公共依赖

[data/cnn_git_v1_protocol.json](../data/cnn_git_v1_protocol.json)是Git可复现入口：保留v8患者折、类别、窗口、训练采样和残差结构，只保留residual_verified一个已评估候选。不是新调参结果或新独立测试。它将辅助来源明确收缩到该候选实际使用的MIT，移除对父缓存/SVDB/LTDB的获取依赖；v8原协议和旧成绩不改。

[prepare_cnn_git.py](../data/prepare_cnn_git.py)直接处理官方原始文件，不读取父train/test.npz；协议逐文件固定SHA256，并固定开发/MIT辅助各字段的张量指纹。新缓存必须逐值复现v8当前候选的输入，否则拒绝完成。字符数组的存储宽度可不同，标签、顺序和数值不允许变。

[train_cnn_cv.py](../data/train_cnn_cv.py)仍使用train_cnn_candidates.py、train_cnn_refined.py及src/reference/ecg_mf_cnn.py的公共函数，以及ecg_trainable_cnn.py/ecg_temporal_cnn.py。它们是当前依赖，不能按文件名旧就删掉。源码/数据/权重/环境和种子随每轮输出保存。旧运行只能在匹配源码副本中重放，不更新旧哈希来掩盖源码变化。

交接必需文件清单由[check_training_checkout.py](../sim/check_training_checkout.py)维护。克隆后该脚本只检查源码和协议，不要求已有tmp。来源/许可与引用见[third_party.md](../third_party.md)，数据不改标项目MIT。Python环境参考本项目既有Python3.14.7/CPU PyTorch2.14.1+cpu，数据重建直接依赖固定为NumPy2.4.4、SciPy1.18.1、WFDB4.3.1，见requirements_cnn_data.txt，不复用未锁版本的QRS安装入口。

## 科学边界与交回要求

- 编号N=0、S=1、V=2、F=3。专家R位置切拍128点/144Hz，约356ms前窗、533ms后窗，当前波形/差分和3个历史RR；训练折单独拟合RR标准化。N不等于健康，四分类不覆盖所有疾病，见[范围记录](records/ecg_scope_20261017.md)。
- 26名INCART开发患者9/9/8三折，同人记录不跨集合；201/202按同人映射。全部42条MIT已参与开发，不能再说成未触碰测试。
- 独立患者incart:10、22、23、31、32、8仍未使用，此入口不下载它们。不得用其选型或调参；先开发达标并冻结最终拟合/测试设计，再安排独立测试。
- 当前没有合格模型。v8残差12,452参数，平均三折macro-F1为0.641363，合并开发OOF为0.623916，S/F F1为0.436667/0.168618。开发折用于停止和选型，因此OOF不是新的独立测试。失败详见[CV记录](records/cnn_patient_cv_20261017.md)。
- 优先审查F患者覆盖及跨来源形态/幅值/标注差异，再立新协议。MIT辅助F800拍中734拍来自两人，不要只加轮次或降低门槛。既有v9—v11失败保留docs/records，专用源码保留本地tmp历史，当前Git入口不依赖它们。
- 新训练提交源码、协议、完整逐类/逐患者指标、混淆矩阵、数据/权重哈希、失败与局限；不要只交准确率截图。目标仍为macro-F1≥0.85，各类F1≥0.70，N/S/V/F召回≥0.95/0.80/0.80/0.70，参数≤100k；这是工程门槛，不是竞赛或临床标准。
- 后续交浮点权重、输入/归一化/张量布局、黄金输入输出，再明确INT8校准范围、缩放/累加/舍入/饱和和逐层误差。当前无全开发最终模型、INT8或PL推理验收。

## Git分工

建议模型负责人独立分支修改data/、分类模型和对应sim测试；板上/PS/PL工作由对应负责人维护，不同时覆盖同一文件。新实验日志放docs/records，README只写工程说明；根README.md和docs/materials_review.md保持原样。

本轮已修正.gitignore，使docs/records的正式过程记录和原始.log可被跟踪；tmp/仍忽略。提交前按`git status`检查新增源码是否纳入、文件迁移删除是否正确，不把旧索引中其他成员改动一并提交。仅文件检查和准备不等于已commit/push，交接时提供实际提交号。

## smoke状态

用户提供的2026-10-17领航者V2上板报告及完整UART已核查，结论为**PASS ECG_SMOKE failures=0**；证据见[上板记录](records/smoke_board_validation_20261017.md)。这是PS→AXI→原检测器→FIFO的合成样本自检，不验证CNN、ADS1292R、真实采集或QSPI掉电启动。早期冻结协议/旧训练产物中的NOT_TESTED是当时快照，不能覆盖这次板上证据；本训练脚本本身仍不执行板卡验证。
