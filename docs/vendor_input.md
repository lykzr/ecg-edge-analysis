# 厂商500Hz心电接入

## 当前入口

客户端“送样 / 双向中转”中的“厂商CSV → Zynq”和“蓝牙采集 → Zynq”默认使用新500Hz ARM程序。用户不再选择右移位数，也无需另跑转换程序。仅旧版回归显式选择`profile=legacy500`；新旧合同不能混用。

固定路线：ADS1292R→STM32→JDY18→USB接收器→电脑→USB_UART→Zynq→电脑。厂商34字节、ECG-IN-1输入和ECG-UART-1结果仍分别解析，电脑不执行QRS或CNN。电脑当前承担量化前去直流及单位换算，不能将这部分计作FPGA滤波或加速。

## 输入处理与保留

1. CSV读取五列RawData的`ecg_raw`，蓝牙读取34字节四点包的CH2。均只减一次8388608；CH1呼吸和厂商滤波列保存但不送入检测。
2. 按卖家确认的标称参考2.42V、增益6换算：`mV = C × 2420 / (6 × 8388607)`。分母取[TI数据手册8.3.8](https://www.ti.com/lit/ds/symlink/ads1292r.pdf)的2^23−1；未进行寄存器读回或实测标定。
3. 在int16量化之前去直流。固定500Hz一阶0.5Hz高通：`a=500/(500+2π×0.5)`，`y[n]=a×(y[n−1]+C[n]−C[n−1])`。第一点初始化`previous=C[0], y[0]=0`，每次新会话重新初始化；这是后向欧拉离散式，不复制厂商滤波系数，也不是厂商0.5～40.5Hz四节带通。
4. 将处理后的标称mV乘4096，按最近整数、半值远离零舍入，饱和到int16并计削顶。源采样率仍500Hz，源编号仍从0逐点连续；不改源节拍、不插值/丢点/压紧缺口。

去直流是必要的量程处理：不能先把包含电极/模拟偏置的绝对电压压到int16，再寄希望于后端滤波恢复波形。去直流具有启动瞬态和相位影响；前5秒仍完整保存、发送和计数，不截掉启动段美化结果，不能把5秒称作质量已经稳定的保证。最终模型还要确认这一前处理合同，不继承公开数据分类准确率。

| 记录 | 含义 |
| --- | --- |
| capture/source.csv或capture/capture.bin | 输入原文，不修改原件 |
| capture/samples.csv | 两通道偏移码、有符号码、厂商滤波列 |
| capture/nominal.csv | CH2原码、处理前标称mV、去直流后mV、int16及本点削顶标记 |
| capture/normalized.csv、normalized.csv | 接收编号和实际转换/拟上传值；确认情况另查根摘要 |
| capture/summary.json、summary.json | 参考电压、增益、滤波初态/系数/来源、削顶、完成/失败、确认/回传及未知上游丢样 |
| results/raw.log | 板端结果，可在主窗口打开日志回放 |

真实采集帧没有源序号和CRC；三帧起始候选不是固件认证。序号连续只能证明本地处理连续。无字节/停流超过5秒、失去帧边界、缓存满、文件写失败或板端确认超时均停止保留现场，不自动重连/重传或补零。

## 启动与使用

当前`releases/latest/runtime500`已是支持ADC的新固件，默认双击其中的`download.cmd`下载；不必先构建，也不需要作者的tmp。唯一匹配bit/XSA/init/ELF及字节/SHA由同目录清单约束。每次完成、停止或掉电后重新下载建立新会话。

也可以从项目根执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -Xsdb '<Vitis>/bin/xsdb.bat' -CableSerial '<唯一JTAG序列号>'
python -B src/ui/main.py
```

入口可加`-CheckOnly`只核文件，不连接板卡。构建/自定义镜像才使用[构建说明](system_checks.md)与`board/start_runtime.py --manifest <新工作区/build_manifest.json>`；tmp/v5adc仅是本机原构建来源，不再是默认下载依赖。历史REPLAY-only版已归档，不能作为本版ADC固件。

主窗口串口保持未连接，在中转子窗口选择Zynq端口。回放选五列厂商RawData；无线选另外一个采集USB接收器端口，不能与Zynq相同，关闭厂商上位机释放端口。来源上图仍画CH2原码，下图画处理后4096单位/mV及板端事件；二者幅值单位不同，不能要求纵轴数值相同。采集USB身份只在解析到候选帧后保存到本机tmp/pc_devices.json；缺席时留空，不按旧COM号盲连。

命令行也复用同一后台：

```powershell
python -B src/pc/ecg_bridge.py --vendor-csv <RawData.csv> --rate 500 --source REPLAY --zynq-port <COM> --output-dir tmp/vendor_replay_new
python -B src/pc/ecg_bridge.py --vendor-port <采集COM> --samples 5000 --rate 500 --source ADC --zynq-port <ZynqCOM> --output-dir tmp/vendor_capture_new
```

原始34字节文件的旧显式位移入口只供legacy500回归，必须添加`--profile legacy500`。标准CSV`index,sample,fs,scale`仍走RuntimeWorker，无去直流或二次换算；不能把已转换的标准CSV再选成厂商RawData。

## 验收与边界

软件回归用`python -B -m unittest discover -s sim -p test_vendor500.py`，包括整数边界、常量偏置不变性、启动/复位、拆包、实际C收发、停止与新会话。板测入口`board/verify_vendor500.py`需明确匹配清单/下载器/USB身份/固定CSV及同源参考；`--simulate-radio`仅把CSV重新编码成34字节，经真实Zynq验证ADC声明，不能称无线通过。

实际结果、第一次全削顶的失败及后续修复见[本轮记录](records/vendor500_20261024.md)。真实采集器、DRDY节拍、实测标定、无线丢样/物理拔插、长时运行和最终模型仍须各自验收；分类未提供保持未知。

## 当前交接与掉电运行

当前500Hz应用已固化到本机板卡QSPI。已写同版镜像时直接QSPI上电，有限会话结束后PS复位；另一块板卡先核对匹配组合，按docs/download_guide.md的QSPI入口操作。JTAG仍是临时下载。完整未完成项统一见report/交接.md，验收见docs/records/qspi_20261025.md；不将数字CSV回放当真实无线、标定或CNN完成。路径均相对仓库根。
