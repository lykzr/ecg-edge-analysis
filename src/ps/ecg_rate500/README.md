# 500Hz源输入的ARM处理核心

本目录接收已明确为500Hz、4096单位/mV的连续int16样本，不解析厂商蓝牙帧。检测内部使用18/25有理FIR衔接360Hz检测流程；事件位置、RR、回传波形和模型切拍都使用500Hz源时轴。它运行在ARM，不是PL分类器。

## 文件

- rate500.c/h与coefficients.h：有界源适配、相位和固定延迟映射；1001抽头Kaiser8.6，20个内部点群延迟，不在EOF补样。
- pipeline500.c与window500.h：源波形环形缓存、RR历史、178点前窗加267点后窗、144Hz/128点模型波形与RR变换。
- 检测器与串口源由build/generate_rate500_runtime.py从冻结360Hz父本生成到新tmp目录，验证父本SHA，不覆盖原目录。500Hz候选增加相邻点复核和有界等待补偿，不声称与360Hz逐事件完全相同。

现有模型窗口协议保持原样：500Hz原波形切拍后36/125重采样，再插值到共同144Hz时间网格，逐拍去均值/std；无最终模型时类别保持未知。不能把右移8位厂商原码当作4096单位/mV。

## 构建与运行

通过board/build_runtime.py显式设置ECG_RUNTIME_RATE=500，选择新的项目tmp短工作区；默认360Hz构建保留。PC使用独立runtime500合同和“500Hz标准CSV → 新QRS”入口，旧厂商500Hz/-1入口仍对应旧应用。步骤与边界见[500Hz说明](../../../docs/rate500.md)。

## 检查

已有QRS依赖与GCC环境运行sim/test_pipeline500.py；FIR逐点检查sim/test_rate500.py需ECG_RATE500_EXE指向通过sim/ecg_rate500_host.c编译的新执行文件。完整配对与窗口检查分别见data/benchmark_rate500.py、data/verify_pipeline500.py。结果在docs/records，不把主机或已知构造数据成绩当实采/实板结论。
