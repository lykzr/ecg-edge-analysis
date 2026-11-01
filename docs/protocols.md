# 当前采集与板端协议

本文件定义 releases/latest 的 runtime500 接口；独立回归程序不自动适用本定义。当前QRS在ARM端运行，未装载最终分类器，没有对外可用的CNN推理接口。

## 采集、单位与时轴

已确认厂商透传帧为34字节：AA BB 后跟4组样本，每组CH1、CH2各4字节大端零扩展24位偏移码。CH1为呼吸，CH2为ECG；有符号码 C=code−8388608。标称500Hz、参考2.42V、增益6，mV=C×2420/(6×8388607)。参考电压与增益尚未实测标定；10字节示例不适用本实物。

电脑对CH2做连续状态0.5Hz高通去直流，再乘4096，按最接近整数、半值远离零舍入，饱和到int16。标准CSV已转换样本不再换算。帧无每样本序号，源端未知丢样计数为−1，不能因此声称无线无丢样。时间以样本位置/500计算，不用电脑收包时间替代。

## ECG-IN-1：送样及确认

ASCII，每行仅LF结束，含换行最多256字节。body后接 * 与8位大写十六进制CRC32；对body字节计算ISO-HDLC CRC32（反射多项式0xEDB88320，初值和最终异或均0xFFFFFFFF），与Python binascii.crc32一致。尖括号仅表示字段：

```text
I,ECG-IN-1,<session>,500,<REPLAY|SYNTH|ADC>,4096*<CRC32>
D,<seq0>,<n>,<sample0>,...*<CRC32>
F,<total>*<CRC32>
A,ECG-IN-1,<session>,<next>,<READY|ACCEPTED|DONE|ERROR>,<reason>*<CRC32>
```

session为会话标识，seq0从0连续，next为下一期待位置。每包n=1..32，样本−32768..32767；整数用规范十进制，不加多余符号或前导零。每会话最多1800000点。发I等READY，每次只保留一包未确认数据，收到ACCEPTED才继续；最后发F等DONE。错误停止，不自动重发。无错误reason为NA，故障为明确原因。

正常DONE后等物理串口发送排空，再重置检测、RR、序号和握手状态，允许下一会话。半行超时2秒、输入空闲5秒、发送阻塞2秒属于故障，不能按正常结束复用。实现见 src/ps/ecg_runtime/link.c 与 src/pc/ 的中转代码。

## ECG-UART-1：结果

ASCII，接收器支持LF/CRLF，每行最多256字节。结果行没有送样协议的CRC后缀。

```text
H,ECG-UART-1,<firmware>,<session>,<source>,<detector>,<fs>,<scale>,<caps>
W,<seq0>,<n>,<raw0>,<filt0>,...
E,<evt>,<rpos>,<rr>,<hr>,<cls>,<conf>
T,<hr>,<rr_ms>,<cls>,<flags>,<fs>,<fifo_event_drop>,<source_sample_drop>,<tx_sample_drop>,<uptime_ms>
L,<level>,<text>
```

H声明量纲/能力；就绪头source=UNKNOWN、detector=QRS26-500-ARM、fs=500、scale=4096、caps=0xD。W每行1..8点，seq0为原输入位置，只回显raw，未提供的filt填NA。E的evt从1递增，rpos为原样本位置，rr为样本数，hr为每分钟心率；首事件rr=0、hr=−1，之后按60×fs/rr计算。cls=?、conf=−1表示没有分类结果。

T的rr_ms为毫秒，与E的rr不同；未知计数为−1，不能当0。L给出就绪、结束和错误说明，不替代A流控。runtime500不接受旧显示命令K；128点心拍和RR等内部准备接口也不表示最终分类模型已经冻结。

## 独立PL回归

smoke/及legacy bridge/使用各自匹配的bit/XSA/ELF，不用于本版ARM检测计分。AXI基地址0x43C00000，完整偏移/位域/FIFO消费顺序见 src/rtl/ecg_qrs_axi_lite.v。legacy500的scale=−1不得混入runtime500。RTL是电路描述，软件参考用于行为核对；保留两者不等于已实现最终FPGA CNN。
