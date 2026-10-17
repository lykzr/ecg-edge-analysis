# 文档拆分后QRS准确性复核（2026-10-16）

按用户要求，将README中的实验日志和成绩迁入docs后，对当前v4重新运行全部42条完整记录。此次是已查看数据的复现检查，不是新的独立测试；没有修改算法、参数、计分、数据划分或既有结果。

## 结果

| 数据角色 | 记录数 | 参考心搏 | TP | FN | FP | 检出率 | 阳性预测值 | V召回 | 位置MAE/ms | 连续匹配RR MAE/ms | 逐记录通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 开发 | 19 | 43941 | 43863 | 78 | 159 | 99.822% | 99.639% | 99.842% | 3.565 | 4.287 | 15/19 |
| 原冻结后评估 | 23 | 52969 | 52892 | 77 | 51 | 99.855% | 99.904% | 99.397% | 2.620 | 1.980 | 20/23 |

与整理前逐项一致：42条记录的全部row字段、两组汇总，以及每条events.csv、positions.csv、matches.csv、missed.csv、extra.csv、summary.json共252份文件逐字节一致。事件输出时刻、位置、RR、类别/时间块计分及确认等待没有变化。

原评估中117位置误差、205/210的V召回仍未通过逐记录门槛；没有降低门槛或因复现一致就改成通过。RR MAE只覆盖连续匹配间期，不能代表漏检/误检区间的完整RR质量。42条范围和起搏/VF等排除项不变，详见[原评估说明](offline_qrs_evaluation.md)。

## 环境与证据

Windows，Python3.14、WFDB4.3.1、NumPy2.4.4、SciPy1.18.1、matplotlib3.10.9，隔离解释器tmp/qrs_benchmark_env/Scripts/python.exe。原始数据tmp/multi_record_20261016_01/raw，运行时重新检查官方SHA256及双通道格式/校验和。当前冻结清单11项实现哈希全部不变。

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B -m unittest discover -s sim -p 'test_*.py'
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/multi_record_20261016_01/raw --stage development --models v4 --output-dir tmp/qrs_recheck_20261016/development
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/multi_record_20261016_01/raw --stage evaluation --models v4 --output-dir tmp/qrs_recheck_20261016/evaluation
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B tmp/qrs_recheck_20261016/verify.py
```

输出目录已有内容时必须换新目录，不覆盖本次证据。23项当前软件检查通过，原始文本日志：[软件测试](qrs_tests_20261016.log)、[开发集重跑](qrs_recheck_development_20261016.log)、[评估集重跑](qrs_recheck_evaluation_20261016.log)。CSV/JSON派生输出与比较脚本在tmp/qrs_recheck_20261016/，核对摘要为verification.json；既有data/results/两份精选结果不改写。

文档修改前快照在tmp/backup/docs_records_20261016/。已检查当前文档链接和发布清单；只更新发布说明的哈希及验证文档的位置，BOOT.BIN、FSBL、bit/XSA/ELF/BIF和原验收状态未变。没有执行Git、CNN训练、RTL/PS修改或Flash写入。

**smoke仍未上板测试。** 此次复核证明文档/文件拆分没有改变软件检测结果，不证明新硬件准确性、分类精度或低延迟。
