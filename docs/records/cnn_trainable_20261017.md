# 可训练轻量CNN连续改进：18组配置仍未合格

日期：2026-10-17。用户要求持续尝试至合格，实在不行明确告知。本轮完成两类网络、18组配置、合计636轮训练；**没有达到本轮预设的严格四分类门槛，未交付分类模型。** 这不是证明所有ECG模型都不可能成功，而是在当前数据范围与路线下没有取得达标证据，不把训练结束或最高总体准确率当通过。

## 授权、环境及安装故障

用户明确允许仅在项目独立环境安装CPU PyTorch及必要依赖。环境位于tmp/cnn_torch_env，Python3.14.7、PyTorch2.14.1+cpu、NumPy2.5.2，4个CPU线程/固定随机种子/确定性算法。QRS原环境未替换，系统Python和驱动未改；不安装CUDA。

首次venv的ensurepip在默认沙箱临时目录写文件被拒；改为进程内TEMP/TMP指向项目tmp/pip_temp后完成引导。普通沙箱无法连接现有代理，获工具权限后从官方CPU索引下载成功，未改代理、ACL或关闭校验。保留[首次输出](cnn_torch_install_20261017.log)、[引导日志](cnn_torch_bootstrap_20261017.log)、[沙箱网络失败](cnn_torch_install_retry_20261017.log)和[成功安装](cnn_torch_install_network_20261017.log)。直接依赖为[data/requirements_cnn.txt](../../data/requirements_cnn.txt)，观察到的完整freeze位于tmp/cnn_torch_requirements_20261017.txt；并非所有列出的包都由本次命令首次引入。

## 方案和验收条件

结构来源和完整命令见[可训练CNN说明](../cnn_trainable.md)。MF路线复用Farag 2023单卷积/GMP/RR分支思路，但卷积全训练；残差路线参考Kachuee等2018的心拍残差Conv1D思路，缩小为三块并增加RR分支，不复制作者源码或权重，不套用论文成绩。

训练前固定本轮工程目标：macro-F1≥0.85、每类F1≥0.70、N/S/V/F召回≥0.95/0.80/0.80/0.70、参数≤100000。目标为助手提出的原型筛选条件，不是用户/比赛/临床要求；没有依据结果降低。

1. v2：6组可训练MF/残差模型，比较原波形/差分/双通道、12/16/32宽度；训练集均衡采样、训练BN。
2. v3：4组，针对训练/验证诊断标准化RR，改自然分布加权损失，并比较去BN及时间/幅值/噪声增强。v3协议继承的augmentation描述不准确；实际增强由各候选augment控制，源码/协议原文保留，不事后改写。
3. v4：4组更长上下文，原360Hz窗口[R-128,R+192)经2/5重采样为128点/144Hz，保留同一受试者角色，只额外排除15个缺外层窗口的N边界心拍（训练6、验证2、测试7）。需要R后约533ms波形等待，不是无等待推理；没有读取后RR标注。
4. v5：4组，延续v2验证表现较好的双通道MF路线，用64点窗口比较RR标准化、自然加权及增强。其设计依据为验证侧的候选表现，不按旧测试挑类别/阈值/偏置。

各轮都保持N/S/V/F、原16/4/22受试者角色及201/202同人隔离；不以随机心拍拆分、删除F、删除困难记录或降低指标来造达标。模板/BN/均值方差/类别权重/采样/增强仅依赖训练数据，权重与候选仅按验证macro-F1选择。每个冻结轮次保存选择后才读取旧测试作一次回放；旧测试从首轮起已经查看，本轮所有回放都是已查看数据上的探索性结果，不构成新的独立验证。

## 每轮结果

| 轮次 | 配置数 | 按验证选择的候选 | 验证macro-F1 | 旧测试回放macro-F1 | 结论 |
| --- | ---: | --- | ---: | ---: | --- |
| cnn_trainable_v2 | 6 | mf_both12 | 0.731651 | 0.565442 | 未达标 |
| cnn_refined_v3 | 4 | residual_both32_no_bn_aug | 0.699682 | 0.596151 | 未达标 |
| cnn_context_v4 | 4 | context_residual_both16_aug | 0.749199 | 0.530255 | 未达标 |
| cnn_mf_refined_v5 | 4 | mf_both24_natural_aug | 0.649906 | 0.596287 | 未达标 |


全18组按验证结果选中`context_residual_both16_aug`，不是选择旧测试分数最高的轮次。额外以完全相同8928个验证心拍身份复核四轮，排序未变，证据tmp/cnn_common_validation_20261017.json。64点与128点轮次的上下文/计算/边界范围不同，不能把其资源和准确率拼成一次优化收益。

所选候选：训练macro-F1=0.952439，验证=0.749199，旧测试=0.530255。参数12452，Conv/Linear算术预算606616 MAC/拍，不含预处理、激活、池化、传输，也不是FPGA综合或实测结果。

| 类别 | 旧测试支持数 | 精确率 | 召回率 | F1 |
| --- | ---: | ---: | ---: | ---: |
| N | 44224 | 96.585% | 92.667% | 0.945854 |
| S | 1837 | 24.141% | 33.642% | 0.281101 |
| V | 3219 | 81.886% | 92.265% | 0.867660 |
| F | 388 | 1.808% | 4.897% | 0.026407 |


所选模型的旧测试总体准确率89.772%；不能以多数N类掩盖S/F失败。完整混淆矩阵、逐记录/各类支持、预测与权重保存在tmp/cnn_context_v4_20261017_01/。没有把其它轮次较好的某一项测试成绩换进所选模型表格，也没有在看到回放后改选其它候选。

## 失败分析和停止当前调参的依据

固定模板首轮在训练侧也几乎不识别S/F；可训练改进中训练macro-F1已能达到0.95以上，但换受试者后显著下降。因此单纯的“没训练成功/只有分类头更新”已不是全部问题，当前证据明确显示泛化不足。

训练S共516拍，其中383拍来自209（74.2%）；F共401拍，其中372拍来自208（92.8%）。F覆盖8条训练记录但其余7条合计仅29拍；验证F只有205一条记录的11拍。心拍总量不能代替独立受试者/形态覆盖。数据集中度是可观察事实，是否为唯一失败原因尚未得到消融证明；不能断言加某一层或加若干数据必然解决。

均衡采样提高了少数类召回，同时可能增加大量N误报；去BN、自然加权、RR标准化、增强和长窗口都未同时保住四类精确率与召回。继续在同一稀少验证F上反复选配置，会增加选择偏差，不能为凑合格继续刷已查看测试。

**结论：本轮没能把这条严格四分类路线做合格。** 保留所有失败，暂不做INT8验收或更新分类发布。下一步需要新的数据/建模与独立评估设计：优先增加S/F独立受试者覆盖或评估预训练迁移的价值，先明确新训练与独立验证来源，再决定是否恢复备选；不能把旧测试转训练后继续用原分数声称泛化，不能不经用户确认删F变三类。此前存下的CLEF仍为备选，本轮未加载。

## 完整配置比较

| 轮次/候选 | 参数数 | 最佳验证轮次 | 实际轮数 | 验证macro-F1 |
| --- | ---: | ---: | ---: | ---: |
| cnn_trainable_v2/mf_derivative12 | 1296 | 6 | 25 | 0.335362 |
| cnn_trainable_v2/residual_raw16 | 12564 | 21 | 36 | 0.318891 |
| cnn_trainable_v2/residual_both16 | 12676 | 15 | 30 | 0.317476 |
| cnn_trainable_v2/mf_both12 | 1680 | 4 | 25 | 0.731651 |
| cnn_trainable_v2/residual_raw32 | 40036 | 15 | 30 | 0.284401 |
| cnn_trainable_v2/residual_both32 | 40260 | 21 | 36 | 0.346913 |
| cnn_refined_v3/mf_deriv_rrstandard | 1296 | 17 | 35 | 0.653129 |
| cnn_refined_v3/residual_raw16_rrstandard | 12564 | 20 | 38 | 0.562594 |
| cnn_refined_v3/residual_both16_no_bn_aug | 12452 | 17 | 35 | 0.606374 |
| cnn_refined_v3/residual_both32_no_bn_aug | 39812 | 29 | 47 | 0.699682 |
| cnn_context_v4/context_mf_both12 | 1680 | 12 | 30 | 0.645608 |
| cnn_context_v4/context_residual_both16_aug | 12452 | 42 | 60 | 0.749199 |
| cnn_context_v4/context_mf_both24_aug | 2532 | 5 | 30 | 0.525327 |
| cnn_context_v4/context_mf_both12_weighted | 1680 | 7 | 30 | 0.563517 |
| cnn_mf_refined_v5/mf_both12_natural | 1680 | 17 | 35 | 0.634309 |
| cnn_mf_refined_v5/mf_both12_natural_aug | 1680 | 13 | 31 | 0.621990 |
| cnn_mf_refined_v5/mf_both24_natural_aug | 2532 | 35 | 53 | 0.649906 |
| cnn_mf_refined_v5/mf_both12_weighted | 1680 | 8 | 30 | 0.617467 |


## 复现与核对证据

- 协议：[v2](../../tmp/history/training_handoff_20261017/data/cnn_trainable_v2_protocol.json)、[v3](../../tmp/history/training_handoff_20261017/data/cnn_refined_v3_protocol.json)、[v4](../../tmp/history/training_handoff_20261017/data/cnn_context_v4_protocol.json)、[v5](../../tmp/history/training_handoff_20261017/data/cnn_mf_refined_v5_protocol.json)。
- 原始训练日志：[v2](cnn_trainable_v2_train_20261017.log)、[v3](cnn_refined_v3_train_20261017.log)、[v4](cnn_context_v4_train_20261017.log)、[v5](cnn_mf_refined_v5_train_20261017.log)；[长上下文准备](cnn_context_prepare_20261017.log)。
- 当前8项PyTorch数值/更新/评估隔离/上下文检查通过，见[检查日志](cnn_context_checks_20261017.log)。原QRS环境37项发现中29项通过、8项因无torch跳过；这8项在新环境实际通过，不能把跳过当通过，见[回归日志](cnn_research_regression_20261017.log)。
- tmp/cnn_trials_verification_20261017.json独立重算所有已保存混淆矩阵和macro-F1，核对协议、运行源码快照、18份权重及按验证选择的候选；决策保存tmp/cnn_research_decision_20261017.json，accepted=false。
- 每轮source_snapshot保留实际运行源码及其原哈希；128点兼容扩展发生在部分64点轮次启动之后，旧轮按自己的快照复现，不拿当前源码哈希冒充历史版本。各轮normalization.json/缓存及源数据哈希均保留。

根README.md、docs/materials_review.md和发布镜像保持原样，QRS冻结11项哈希不变；没有Git、Computer Use、板卡/Flash或多人分派。**smoke仍未上板测试。**
