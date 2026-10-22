# 启动学习与候选峰修复

该候选修复原检测器的两个结构问题：固定初始能量尺度与实际输入不匹配；只看能量上穿阈值时，持续高于阈值的能量无法再次触发。原src/rtl/ecg_qrs_detector.sv与smoke保持独立。

## 当前实现

- 输入仍为现有原生int16码；厂商入口保留24位原码，CH2减8388608后算术右移8位。没有物理标定时scale=-1，不把启动统计解释成mV。
- 前两秒按有效样本推进能量与原始位置，只学习完整积分窗口的能量均值/最大值，不输出事件。启动噪声取Q32向下倒数乘法近似均值（至少1），信号取最大值且至少比噪声大1。当前360/500Hz配置的累加上界小于2^32，32位累加不溢出；近似整数均值相对精确除法最多低1能量码。这样避免64位组合除法的时序代价，软件参考同步使用相同规则。没有增益搜索、标注辅助或整段未来访问。
- 预热后用局部能量峰与自适应阈值比较，只有候选峰更新信号/噪声估计，保留200ms不应期。平顶取下降侧确认；位置仍是积分窗中心近似，不是精确R峰。
- 首RR未知；启动、复位、暂停及样本位置不压紧。不读满两秒的会话不强行生成事件。输入缺失仍按既有协议停止留证，不擅自补零或自动重连。
- 本次没有把滤波写成已部署：原差分对常量基线不敏感，但不代表已解决工频、运动伪迹或最终抗噪。滤波/定点化仍按采集A06独立推进，不为产生事件选择处理分支。

## 源码与构建

整数参考src/reference/ecg_auto.py，RTL为src/rtl/ecg_qrs_auto.sv。build/build_ecg_auto.tcl从原AXI接口生成仅替换检测器实例的独立工程，冻结本次源快照；PS/DDR/MIO/时钟和寄存器地址不变。调用Vivado batch时传入一个不存在的项目tmp目录。

board/build_ecg_auto.py由Vitis Python执行，环境变量ECG_AUTO_HARDWARE指向匹配hardware，ECG_AUTO_WORKSPACE指向新的工作区。它从既有PS核心生成候选副本，仅修改H身份和预热L说明；生成/原始源码SHA分别记录，不修改旧应用或假装是新手写核心。

候选身份ps-auto-1/QRS-AUTOPEAK-60，H.caps仍0xD，W.filt=NA、scale=-1、cls/conf=?/-1。ECG-IN-1与ECG-UART-1格式不变，电脑只显式接受原版和本候选两种身份，未知检测器仍拒绝。收到预热说明不代表已检出心拍或准确率通过。

## 检查与边界

sim/test_qrs_auto.py检查低幅/极性、静默/DC、暂停/复位、因果和协议身份；sim/check_qrs_auto.py逐周期比较实际RTL与整数参考，并完整复跑100/101/103已知开发记录。data/evaluate_qrs_auto.py扩展到既有19条开发记录，保留逐记录、标注类型、时间块与全部错漏位置，不修改原v4协议、不读取新的独立测试、也不恢复CNN训练。

成功出现事件不等于检测准确率合格。第一版仅修启动初值在完整标注回归失败，保留其源码/输出；当前候选另行验证。发布/实板/开发指标等实际结果集中[修复记录](records/qrs_auto_20261021.md)，不写入README冒充最终验收。


## 离线复跑与候选工作区

先准备现有开发记录与用户CSV派生输入，替换下列路径；输出目录须不存在。最后两步只构建，不连接板卡。

```powershell
python -B -m unittest discover -s sim -p test_qrs_auto.py -v
python -B sim/check_qrs_auto.py --output tmp/auto_check_new --vivado-bin '<Vivado目录>/bin' --raw '<已获取MIT开发记录目录>' --csv-input '<含sample列的原shift8派生CSV>'
python -B data/evaluate_qrs_auto.py --raw '<已获取MIT开发记录目录>' --output tmp/auto_development_new
python -B sim/check_auto_bridge.py --output tmp/auto_host_new --csv-input '<含sample列的原shift8派生CSV>'
& '<Vivado目录>/bin/vivado.bat' -mode batch -source build/build_ecg_auto.tcl -tclargs '<项目绝对路径>/tmp/auto_build_new'
$env:ECG_AUTO_HARDWARE='<项目绝对路径>/tmp/auto_build_new/hardware'
$env:ECG_AUTO_WORKSPACE='<项目绝对路径>/tmp/ecg_auto_new/w'
& '<Vitis目录>/bin/vitis.bat' -s board/build_ecg_auto.py
```

check_qrs_auto.py的--csv-input可替换用户输入位置，未传时沿用本机已保留的10412点CSV证据；其他电脑需要获取实际输入，不用合成波形冒充该记录。check_auto_bridge.py直接接受CSV路径，使用实际生成的候选PS C、假串口及整数AXI参考核对上传/确认/回传、事件/RR、预热说明与完整结束，不等于ARM或PL实板运行。

启动均值计算在1000个有效样本后再经过3个内部时钟提交；这3拍仍接收并记录样本，不作事件判决，源位置不压缩。正常500Hz输入的样本间隔远长于3个100MHz时钟；离线参考刻意也检查连续有效时钟。上板应核对此行为而不是提前补事件。

新工作区组件为ecg_platform与ecg_auto，运行配置ecg_auto_app_hw_1默认启用系统复位和重配PL。不要在旧bridge工作区只替换ELF：必须整套匹配候选bit/XSA/ps7_init/ELF。现有已验发布不含新候选，最新构建与时序状态以修复记录为准。

Windows工作区路径需足够短，BSP内部层级很深；脚本会预检已知最长依赖路径并拒绝超过安全长度的输入。本机最终候选工作区为tmp/ecg_auto/w；较深的tmp/qrs_auto_20261021/firmware_v4/vitis_workspace构建失败，仍保留原目录作为证据。不要搬动正在构建的工作区。


后续原波形定位/质量确认另见[说明](qrs_peak.md)。它是独立软件研究候选，未进入本页ecg_auto工作区或匹配RTL/ELF，不把其定位成绩套给当前镜像。
