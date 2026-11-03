---
name: trace-check
description: 对同一时轴的软件、C或RTL导出CSV逐行比对，按预先确定的容差报告首个不同字段。
---

# 黄金参考比对

适用：独立参考与待验证实现能导出相同字段、相同行顺序的CSV。可用于滤波、控制、通信计数或整数算子；不依赖ECG、Vivado或特定模型。Python3.10及以上标准库即可运行。

## 比较前先固定合同

列明复位、有效拍/空拍、源序号、位宽、符号、溢出、舍入与输出延迟。同步RTL按旧状态计算本拍输出，再提交新状态；不能用任意平移、删头尾或只挑共同事件使结果一致。整数默认精确比较；浮点容差在看本次差异前确定。

## 使用

两侧导出相同顺序的唯一非空表头，例如`cycle,valid,value`。键列要求文本精确相等，避免把不同周期误当相同；其他数字按`abs(实际-参考) <= atol + rtol*abs(参考)`，文本精确比较。

从本技能子目录（包含SKILL.md和scripts的目录）运行；输入路径相对当前工作目录，也可用绝对路径。

```text
python scripts/compare_csv.py --reference golden.csv --candidate actual.csv --key cycle
python scripts/compare_csv.py --reference golden.csv --candidate actual.csv --key cycle --atol 0.000001 --rtol 0
```

默认容差0。通过退出0；首个差异返回行号/字段/两侧值并退出1。行数/表头不同、空数据、缺失字段、NaN/Infinity均不能报通过。多个键重复传--key。脚本不重采样、不对齐、不改输入文件。

## 效果与来源

原ECG逐周期对照覆盖有效拍、复位、负数右移与状态更新顺序，项目模板为`sim/check_ecg_reference.py`和`sim/tb_ecg_reference.sv`。它是原检测器验证，不是当前ARM研究26准确率。通用CSV脚本另验证整数一致、错误周期、单字段差异、容差、行数/表头/非有限值拒绝；本轮用例见仓库 `skill/tests/test_portable.py`、结果见 `skill/validation.json`，无需依赖原工程即可使用脚本。没有宣称新脚本重新跑过所有ECG RTL/XSim。

## 失效条件

两侧共用同一个错误也会一致；参考正确性和独立性须另审。参考比对不等于专家标注的检测准确率，不等于分类macro-F1、板上运行或真实传感器效果。异步日志、丢失键或不同时轴必须先查采集原因，不能自动拼齐。整数文本在零容差时用Python整数精确比较；科学计数法、小数及非零容差使用双精度，不用于要求任意精度小数的合同。
