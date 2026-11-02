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

## 网页电脑端HGB分析

POST /api/v1/live/sessions支持analyze_when_complete（默认true）及standard_preprocess（仅标准500Hz，hp05/raw；未声明拒绝分析）。厂商来源固定完整CH2原码→标称mV→hp05。采集关闭后自动提交现有记录任务；会话快照analysis给waiting/submitted/failed、task_id和error。

POST /api/v1/live/sessions/{id}/analyze接受JSON对象，可对自己的已保存会话手动提交。重复请求复用同一模型/预处理任务，保持账户隔离。分析结果经原tasks/records接口查询；prediction.task_type=beat_level、execution_location=host_pc、qualified=false，beats.items保留逐拍位置、有效性、N/S/VF和概率。未分类保留UNCLASSIFIED/null，不用N替代。

板端事件关联只在±25点双向唯一时成立，board_event_id、board_r_sample500、board_delta_samples分别保留关联身份及模型位置减板端位置的差；无唯一对应时返回null。它不是检测准确率，不改变ECG-1或固件NO_MODEL/?，也不提供专家标注。完整输入和限制见[模型接入](model_integration.md)。

## 独立PL回归

smoke/及legacy bridge/使用各自匹配的bit/XSA/ELF，不用于本版ARM检测计分。AXI基地址0x43C00000，完整偏移/位域/FIFO消费顺序见 src/rtl/ecg_qrs_axi_lite.v。legacy500的scale=−1不得混入runtime500。RTL是电路描述，软件参考用于行为核对；保留两者不等于已实现最终FPGA CNN。

## 独立ARM模型批处理：HGB-BATCH-1

这是`src/ps/ecg_hgb/main.c`与`src/pc/ecg_hgb.py`的独立候选协议，不兼容网页当前ECG-IN-1/ECG-UART-1，不接厂商34字节。USB_UART为115200/8N1/无流控。输入固定500Hz、单导联mV；hp05表示原始mV由ARM执行指定高通，raw仅接严格匹配高通后的mV。三类为N/S/VF，VF是V/E/F合并；研究模型未全部达标，不能解释为疾病诊断。

```text
H,HGB-BATCH-1,READY,500,mV,<model_sha256>
I,HGB-BATCH-1,<sid>,500,mV,<hp05|raw>,<total>
A,<sid>,READY,32
B,<sid>,<offset>,<count>,<crc32_hex>
<count个little-endian float64 mV，无分隔符>
A,<sid>,NEXT,<new_offset>
D,<sid>,<total>
R,<sid>,<beat_id>,<position>,<ready_at>,<decision_at>,<status>,<class_id>,<pN_hex>,<pS_hex>,<pVF_hex>
D,<sid>,<total>,<events>,<clipped>,<input_us>,<prepare_us>,<classify_us>
```

sid为非零uint32，total为1—30000，count为1—32且不得超过剩余数。offset从0严格连续，不重发/跳包；每块收到NEXT后才发下一块，保证背压。CRC为该块原始二进制的标准CRC32（与zlib.crc32一致）；每个值必须有限。普通分块保持高通状态；记录结束才整段检测/重切拍、192项特征和分类。事件上限480，工作区512KiB，容量不足明确失败。完整记录最多60秒，不是循环流或实时逐拍返回。

beat_id从1递增；position/ready_at/decision_at均为该会话500Hz、0起点样本位置，分别为模型定位、切窗就绪和含后继信息的决定时刻。status=0有效，class_id=0/1/2对应N/S/VF；status=2窗口不足、4首RR未知时class_id=-1且三概率NaN。概率字段为double位型的16位十六进制文本，高位先写；电脑转换未知为null，不能补成N。这些编号来自模型自身重切拍，不自动等于现有QRS事件号。

接收块期间`X,<sid>`取消并返回`S,<sid>,CANCEL`。错误返回`F,<sid>,<reason>`（头错误sid=0），停止该会话；等待头/块体/结束最多10秒，发送等待最多4秒。空闲每2秒重复READY，正常完成/明确失败/取消均回到等待新会话。错误率、CRC、取消、空闲超时后的新会话已受控验证；物理拔插、半包后任意残留字节重同步未验，不承诺自动续传。来源缺样、设备/增益/导联变化必须终止并开新记录，不插值或跨断点连RR。

clipped为mV量化到int16时的饱和点数，不是无线丢样数；三项us仅统计ARM输入换算、检测切拍、特征分类计算，不包括串口与等待，不用于宣称加速比。输出为ASCII且无独立CRC；电脑验证会话/时轴/计数/概率，尚不能代替链路完整性全面验收。输入原文件、tx.bin、rx.log及result.json保留独立收据，按冻结参考另做数值核对。该程序仅临时JTAG，尚未更新Flash或latest。

## H27四分类训练交接合同（独立候选）

固定协议为[cnn_fourclass/protocol.json](../model/cnn_fourclass/protocol.json)，特征顺序为[feature_names.json](../model/cnn_fourclass/feature_names.json)。四输出N/S/V/F，N不代表健康，F不删除或合并；优先完整自动链N/S/V平均F1，同时报告四类、逐患者、漏失列及额外预测。26名INCART开发患者三折隔离，MIT-BIH辅助仅训练，201/202同人，六名封存患者不读。HGB三类概率仅作训练期蒸馏，不能当四类真标签。

单次当前拍CNN及因果历史特征共269维，500Hz原始mV首选hp05，匹配0.5Hz因果高通才用raw；不接网页零相位显示列或其他未核滤波。128点切拍、已完成历史背景和RR8的精确定义见源码及接手说明。整段电脑参考每次重建状态，不代表实时跨块、INT8或FPGA实现。此合同不修改现有三类HGB接口及固件发布。
