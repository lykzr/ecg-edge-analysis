# QRS研究快照与便携复现

src/reference/qrs_research为未合格研究26的源码快照；保留原始文件SHA与仅导入/来源注释改动映射。它从同一输入重新运行两个检测源并做200ms截止后处理，不依赖本机tmp事件CSV。当前未整体合格；未完成完整在线运行时、500Hz/幅值/整数/PS/RTL及新上板验收。

依赖使用data/requirements_qrs.txt中的WFDB及现有NumPy/SciPy环境；版本固定/实际环境见记录，安装须另依操作者授权。任意英文目录可放项目，用项目根运行，Python路径换成操作者自己的解释器：

```powershell
python -B sim/check_checkout.py
python -B data/benchmark_qrs_research.py --raw-dir <mit_raw_dir> --output-dir <new_output_dir> --stage development
python -B data/benchmark_qrs_research.py --raw-dir <mit_raw_dir> --output-dir <another_new_output_dir> --stage evaluation
```

数据由data/download_mitdb_records.py获取并核官方SHA，原始数据不随源码交接。两个stage均是已知开发回归；不能改称独立测试。输出目录必须不存在，脚本不会覆盖。新协议去掉历史v5内过期的untouched里程碑口径；历史协议原字节保留，不重写旧成绩。

研究原型保留诊断audit列表；整个重放保存全输入/源事件，不承诺内存有界，也不作为release。WFDB派生核心许可见src/third_party/wfdb_license.txt。gradient参考NeuroKit固定commit的原默认梯度思路，重新实现有界历史宽度估计，并非原函数数值等价；未复制GPL Hamilton等实现。来源在provenance.json。

受控噪声下一步见[评估计划](../report/project_plan.md#评估修正与三天工作安排)，DS只做[隔离任务](ds_task.md)。正式可交接文件由sim/checkout_files.json列举；历史尝试和原始数据留本地tmp，不是交接依赖。
