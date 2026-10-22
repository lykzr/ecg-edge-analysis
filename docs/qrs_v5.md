# 成熟QRS参考的独立改进候选

本候选继承现有MIT许可GQRS及v4的有界逐点处理，在候选支路增加40Hz因果低通，再对同极性连续平台上的双峰改进原波形定位。它输出心拍位置和RR，不做CNN分类。旧v4、auto、peak与已验板端程序分别保留，不能互相继承验收结果。

## 接口和输入

`src/reference/ecg_qrs_v5.py`的`Detector(ShapeConfig())`接收有符号int16；`push(value)`返回零个或多个`(emission_index, index, rr_samples)`。首RR为0表示未知；序号从0开始。`valid=False`不推进任何滤波或采样状态，`reset_n=False`清空所有状态。收到多少样本就处理多少，不在文件结束补零。

当前只允许已核对的360Hz、4096单位/mV，不等于厂商500Hz原码、右移8位预览或直接插上板卡即可用。500Hz、实际ADC幅值映射及PS/PL部署还要分别验证，不能直接移除旧配置的采样率检查来宣称完成。

## 处理规则

- GQRS候选输入经过既有双二阶40Hz低通，以对称四舍五入和饱和转回int16。原始输入仍单独保存，定位、背景质量及宽波确认继续读原码，不按滤波延迟平移标签。
- 沿用v4原波形定位。仅当两个显著极值同极性、相距不超过80ms，且连接处相对基线的幅值一直不低于较小峰幅度的一半时，选择更强的极值；其他形态沿用原选择。它处理的是同一高平台上的分裂峰，不将不同极性的波峰合并。
- 原不应期、候选回搜、中心/背景和宽波救援规则保留。原码、变化量和滤波输入各4096槽，内部平滑/QRS各1024槽、64峰槽；有界不等于已做整数化或时序分析。
- 继承GQRS的补报机制，样本确认等待可明显长于普通输出。确认等待以实际输入/事件序号差计算，不能称为ARM/FPGA执行时间或整机延迟。

## 运行和复核

先准备[data/requirements_qrs.txt](../data/requirements_qrs.txt)要求的隔离环境及已有MIT-BIH原始数据。解释器路径因电脑而异，示例`python`应替换为该环境的Python。

```powershell
python -B -m unittest discover -s sim -p test_qrs_v5.py -v
python -B data/benchmark_qrs_v5.py --raw-dir '<原始记录目录>' --stage development --output-dir tmp/qrs_v5_development_new
python -B data/benchmark_qrs_v5.py --raw-dir '<原始记录目录>' --stage evaluation --output-dir tmp/qrs_v5_evaluation_new
```

输出目录存在即停止，不覆盖证据。入口核对完整冻结依赖、官方数据SHA、原记录/幅值/匹配容差/门槛，输出逐记录、类型、时间块、位置、RR、全部错漏和确认等待。19条开发及原23条评估都已经查看，`evaluation`只是沿用记录角色的参数名，本次属于已知数据回归，不是新独立测试，不使用CNN保留测试集。

## 使用边界

本候选包含浮点质量判断和Python/WFDB状态，尚无匹配C、RTL、bit/XSA/ELF或上板结果。未合格方案不替换`releases/latest/`。接板前必须确认采样率、幅值合同、来源匹配及实际实现，不能下载旧auto镜像来代替本模块验证。

试验、失败和采用理由见[本轮记录](records/qrs_continue_20261021.md)。
