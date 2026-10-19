# 电脑双向中转使用说明

相关文件按同一功能命名：电脑入口`src/pc/ecg_bridge.py`，配套模块`ecg_bridge_core.py`、`ecg_bridge_protocol.py`、`ecg_bridge_capture.py`、`ecg_bridge_serial.py`；板端目录`src/ps/ecg_bridge/`，构建入口`board/build_ecg_bridge.py`，离线测试`sim/test_ecg_bridge.py`及其C适配`sim/ecg_bridge_host.c`。本文讲操作，[bridge_protocol.md](bridge_protocol.md)讲输入协议；结果协议仍单独见`uart_protocol.md`。

中转路线和字段见[ECG-IN-1](bridge_protocol.md)，板端结果见[ECG-UART-1](uart_protocol.md)。独立命令行入口为src/pc/ecg_bridge.py；现有Tk监视器仍是结果接收/回放界面，本轮未增加双连接操作控件。先用命令行保留完整证据，结果可用原界面回放；不声称已经实现蓝牙实时GUI联调。

## 离线检查

从项目根目录使用已有Python及GCC，无需安装依赖：

```powershell
python -B -m unittest discover -s sim -p test_ecg_bridge.py -v
```

该检查编译实际PS bridge.c，共享库加载后注入模拟串口/AXI，AXI检测行为由原检测器500Hz整数参考提供；不是RTL仿真或真实板卡。还直接运行中转CLI的厂商文件和模拟实时采集分支，验证原码保留及结果分流。产物保留tmp/usb_bridge_tests/的独立目录，不清理历史。

## 构建板端接收应用

复用已生成的500Hz硬件；如尚未生成，先运行build/stream_500.tcl（已有目录不覆盖，见[PS说明](ps_stream.md)）。然后使用Vitis自带Python：

```powershell
& '<Vitis安装目录>/bin/vitis.bat' -s board/build_ecg_bridge.py
```

默认新工作区为tmp/ecg_bridge/vitis_workspace，组件为ecg_platform和ecg_bridge，启动配置ecg_bridge_app_hw_1。已有目录即停止；可在当前终端设置ECG_STREAM_WORKSPACE为新的英文路径。硬件默认tmp/ecg_stream_500/hardware；自定义XSA时必须同时指定匹配的ECG_STREAM_BIT/ECG_STREAM_PSINIT，不能使用latest的360Hz组合。

应用等待电脑I初始化，不自己造样本；新会话前必须系统复位并重新配置500Hz PL。保持既有JTAG下载流程，不写Flash，不覆盖smoke。当前构建成功不等于上板已通过。

## 电脑送入已转换的500Hz样本

CSV包含sample列，可另有从0连续的index和恒为500的fs列；sample须为规范int16整数。不自动重采样或标定。端口按实物替换，不固定COM14：

```powershell
python -B src/pc/ecg_bridge.py --csv '<500Hz算法输入.csv>' --source REPLAY --rate 500 --zynq-port COM14 --output-dir tmp/bridge_csv_new
```

输出目录必须不存在。一个进程同时读写同一USB_UART，关闭Vitis串口终端等占用程序。板端必须已运行本次ecg_bridge且等待I，不能运行旧ecg_stream或Hello World。当前严格会话不自动跳过启动杂字节、清空接收缓冲或复位板卡；若收到旧日志/错误协议，保存失败现场后核对应用及启动顺序。

## 厂商采集数据入口

已有从完整帧边界开始的二进制记录时，可离线解码并转发：

```powershell
python -B src/pc/ecg_bridge.py --vendor-log '<厂商原文.bin>' --format source_10 --channel 1 --shift 8 --aligned --source REPLAY --rate 500 --zynq-port COM14 --output-dir tmp/bridge_vendor_new
```

此处channel=1、shift=8只演示参数语法，不是已确认的ECG通道或标定配置。程序先保留两个24位通道，再按指定通道算术右移并饱和至int16，计削顶；不会根据波形猜通道。DOCX版本需显式改为document_34，不自动识别。--aligned表示调用者已确认初始边界；若无法确认，不应使用该开关伪造条件。数据内可能出现AA BB，格式合法仍不能证明无误码。

只有确认蓝牙提供串口透传虚拟COM之后，才能用实时采集分支；任意BLE设备不能直接套用：

```powershell
python -B src/pc/ecg_bridge.py --vendor-port COM20 --format source_10 --channel 1 --shift 8 --aligned --samples 5003 --source ADC --rate 500 --zynq-port COM14 --output-dir tmp/bridge_live_new
```

采集COM与USB_UART COM必须不同；实时分支须限制本次点数，持续排空采集端并保存。蓝牙类型/配对方式、实际厂商固件、源帧起点和真实节拍仍未核实，以上不是当前实物可直接运行的承诺。source=ADC只是发送者声明。到样本上限后结束本次会话，不控制STM32停止；最后一帧额外观察的点保留原码但可能未转发，摘要分开记录observed/source_samples/confirmed。

## 记录和成功判据

每次记录独立目录，默认所有原文和CSV合计最多64MiB，达到限额停止；摘要不计入数据限额。不会覆盖旧数据、自动轮转或删除历史。

| 文件 | 含义 |
| --- | --- |
| capture.bin、adc.csv | 厂商入口原始字节及电脑接收编号/两个24位码；不是ADC源计数 |
| input.csv | CSV入口原件副本；厂商入口时为空，不假造CSV来源 |
| normalized.csv | 本次选择并转换后拟送入的int16/输入编号；不等于已确认送达 |
| upload.log | 写驱动成功报告的输入协议字节；不证明物理线已发送，写失败时输出状态可能不确定 |
| usb_rx.log | USB_UART实际读取字节，含控制确认及结果 |
| controls.log | 从USB读取字节中分出的A确认，仍保留CRC |
| results/raw.log与CSV | 仅H/W/E/T/L结果流，供既有监视器回放；不混入A或厂商原文 |
| summary.json | 完成/失败原因、拟送/确认/回传数量、队列峰值、削顶及未知源丢样边界 |

正常成功必须同时满足READY→逐包ACCEPTED→最终DONE、回传样本逐值/序号一致、事件序号/RR/位置一致、完整END统计、无已知丢弃/解析错误，并且记录及连接关闭成功。无法证明上游未丢样时保持未知，不填0。坏CRC/重复/乱序/残帧/队列满/超时即停止留证，不自动重传或补零。

查看回传波形时启动原PC监视器，选择“打开日志回放”，打开本次results/raw.log；原始24位采集码保存在adc.csv，结果W为提交Zynq的16位码，不能混为同一幅值单位。**真实蓝牙、USB全双工、PL运算与持续运行都还未上板验收。**
