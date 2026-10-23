# QRS研究快照与便携复现

> 当前决定：2026-10-23暂停QRS算法调优/训练与新搜索，保留阶段基线及失败标签；后续优先接口与系统集成。详见[暂停决定与风险](../report/system.md#qrs暂停决定与风险)。以下回归命令供需要时复现，不作为自动继续试验的指令。

**当前采用结果（2026-10-23）**：研究26 完整42条已知开发回归 41/42（开发18/19、原评估23/23），105 仍因噪声误检未过；本次复测与第26轮一致，数据SHA未变。详见[复测与采用记录](records/qrs_research26_20261023.md)和[固化结果](../data/results/qrs_research26_20261023.json)。该结果是已知数据复现，不是独立测试，也不表示整体合格；不再为105做阈值/特例调参。

src/reference/qrs_research为未合格研究26的源码快照；保留原始文件SHA与仅导入/来源注释改动映射。它从同一输入重新运行两个检测源并做200ms截止后处理，不依赖本机tmp事件CSV。本冻结入口仍是离线重放；新增逐样本运行时候选及500Hz/切拍的验收另见[运行时说明](qrs_runtime.md)，整数PS/RTL及新上板仍未验收，算法未整体合格。

依赖使用data/requirements_qrs.txt中的WFDB及现有NumPy/SciPy环境；版本固定/实际环境见记录，安装须另依操作者授权。任意英文目录可放项目，用项目根运行，Python路径换成操作者自己的解释器：

```powershell
python -B sim/check_checkout.py
python -B data/benchmark_qrs_research.py --raw-dir <mit_raw_dir> --output-dir <new_output_dir> --stage development
python -B data/benchmark_qrs_research.py --raw-dir <mit_raw_dir> --output-dir <another_new_output_dir> --stage evaluation
```

数据由data/download_mitdb_records.py获取并核官方SHA，原始数据不随源码交接。两个stage均是已知开发回归；不能改称独立测试。输出目录必须不存在，脚本不会覆盖。新协议去掉历史v5内过期的untouched里程碑口径；历史协议原字节保留，不重写旧成绩。

研究原型保留诊断audit列表；整个重放保存全输入/源事件，不承诺内存有界，也不作为release。另建的[逐样本运行时与切拍](qrs_runtime.md)不改本冻结快照，其360Hz等价、500Hz适配及部署阶段分别验收。WFDB派生核心许可见src/third_party/wfdb_license.txt。gradient参考NeuroKit固定commit的原默认梯度思路，重新实现有界历史宽度估计，并非原函数数值等价；未复制GPL Hamilton等实现。来源在provenance.json。

受控噪声原排期已暂停，已完成证据保留；后续顺序见[当前计划](../report/project_plan.md#qrs暂停后的实施顺序)。[DS隔离任务](ds_task.md)仅作历史入口，不自动重启。正式可交接文件由sim/checkout_files.json列举；历史尝试和原始数据留本地tmp，不是交接依赖。
