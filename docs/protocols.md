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

这是`src/ps/ecg_hgb/main.c`与`src/pc/ecg_hgb.py`的独立报文协议。双协议候选固件同时保留ECG-IN-1/ECG-UART-1，但一次只执行一个会话，不能混发；不直接接厂商34字节。USB_UART为115200/8N1/无流控。输入固定500Hz、单导联mV；hp05表示原始mV由ARM执行指定高通，raw仅接严格匹配高通后的mV。三类为N/S/VF，VF是V/E/F合并；研究模型未全部达标，不能解释为疾病诊断。

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

beat_id从1递增；position/ready_at/decision_at均为该会话500Hz、0起点样本位置，分别为模型定位、切窗就绪和含后继信息的决定时刻。status=0有效，class_id=0/1/2对应N/S/VF；status=2首RR未知、4窗口不足时class_id=-1且三概率NaN。概率字段为double位型的16位十六进制文本，高位先写；电脑转换未知为null，不能补成N。这些编号来自模型自身重切拍，不自动等于现有QRS事件号。

接收块期间`X,<sid>`取消并返回`S,<sid>,CANCEL`。错误返回`F,<sid>,<reason>`（头错误sid=0），停止该会话；等待头/块体/结束最多10秒，发送等待最多4秒。双协议空闲每2秒广播原ECG-UART-1就绪头；收到合法HGB的I后先发HGB模型READY，再发A。这样原客户端不用识别三类模型协议，新增客户端仍验证固定模型身份。正常完成不立即追加H，以免污染原客户端DONE检查。HGB正常完成/明确失败/取消回到等待新会话，原实时协议故障仍停止。错误率、CRC、取消、空闲超时后的新会话已受控验证；物理拔插、半包后任意残留字节重同步未验，不承诺自动续传。来源缺样、设备/增益/导联变化必须终止并开新记录，不插值或跨断点连RR。

clipped为mV量化到int16时的饱和点数，不是无线丢样数；三项us仅统计ARM输入换算、检测切拍、特征分类计算，不包括串口与等待，不用于宣称加速比。输出为ASCII且无独立CRC；电脑验证会话/时轴/计数/概率，尚不能代替链路完整性全面验收。输入原文件、tx.bin、rx.log及result.json保留独立收据，按冻结参考另做数值核对。下载、Flash与发布状态以[当前报告](../report/report.md)及匹配清单为准。

### 网页板端模型接线

POST /api/v1/live/sessions新增`board_model`布尔值，默认false；只允许standard500、bridge_csv、bridge_serial。standard500必须声明standard_preprocess，厂商输入固定原始CH2→标称mV→ARM hp05，不使用显示滤波列。采集模式上限1—30000点，文件超30000点拒绝，不截断后冒称完整分类。收齐输入后才打开Zynq送样；不能将此模式用于连续实时分类。

快照保留`board_model=true`、`info.execution_location=zynq_arm`、固定模型SHA与qualified=false；结果单独解析N/S/VF及UNCLASSIFIED，不修改ECG-UART-1四类解析器。模型拥有自己的beat_id和position，不回填或覆盖原QRS的事件号。完整result.json保留全部事件，页面只绘制末4096点/256事件。波形注明`host_input`，是送板mV而非板端回显；confirmed只证明收样确认，不能据此填echoed。

`analyze_when_complete`仍独立控制电脑端报告分析。即使同时启用，板载结果的execution_location和电脑端的host_pc分别保留；电脑分析读取完整原文件与板端完整result.json，不使用页面缓存。保存input_mv.csv、输入SHA、发送/接收原始记录及summary.json，所有者隔离和停止保存规则继续生效。

PC只在发送I之前执行最多10秒/8192字节的完整就绪头同步，允许上电时杂字节前缀，原字节留rx.log与startup_discard.bin。错误就绪身份拒绝，不发送样本；启动头之后的应答、序号、CRC与ASCII均按严格会话规则检查。该有限同步不等于活动会话坏字节重同步或断线续传。


## HGB PL候选扩展

PL候选空闲广播`H,HGB-PL-1,READY,500,mV,<model_sha256>`，同一候选仍接收HGB-BATCH-1的I/B/D输入及原实时入口。客户端必须先识别该身份才接受性能报文；旧ARM固件继续使用既有身份，不因板卡名称或网页选项猜测PL执行。模型SHA标识原始权重，候选精度另标Q40。

成功分类后、R结果之前返回一行：

```text
P,<sid>,Q40,<beats>,<mismatches>,<arm_ticks>,<pl_call_ticks>,<pl_core_cycles>,<timer_hz>,100000000
```

beats仅计status=0的有效分类拍，须与完整R记录数量一致。两端采用相同float32比较及Q40分数；任何分数不一致或PL超时直接分类失败，不返回成功结果。P只能出现一次，缺P、重复P、非PL身份携带P、非法频率/计数均拒绝。零有效拍时累计计数为零、平均及加速比为null。PL_call包括192项写入、启动、轮询及3项64位分数读取，PL_core是100MHz核周期；ARM_ticks测同一输入的Q40软件树遍历。两者均不含softmax、检测/特征、串口等待；整段classify_us还包含特征生成、两端计算和概率换算，不能作为纯PL耗时。

电脑result.json及网页info增加execution_location（zynq_pl/zynq_arm）、precision及performance原始计数与派生指标。网页必须以成功报文确定执行位置，尚无完整结果时显示等待；旧记录缺字段不伪造成PL。研究质量边界及VF合并含义不变。


## H27四分类训练交接合同（独立候选）

固定协议为[cnn_fourclass/protocol.json](../model/cnn_fourclass/protocol.json)，特征顺序为[feature_names.json](../model/cnn_fourclass/feature_names.json)。四输出N/S/V/F，N不代表健康，F不删除或合并；优先完整自动链N/S/V平均F1，同时报告四类、逐患者、漏失列及额外预测。26名INCART开发患者三折隔离，MIT-BIH辅助仅训练，201/202同人，六名封存患者不读。HGB三类概率仅作训练期蒸馏，不能当四类真标签。

单次当前拍CNN及因果历史特征共269维，500Hz原始mV首选hp05，匹配0.5Hz因果高通才用raw；不接网页零相位显示列或其他未核滤波。128点切拍、已完成历史背景和RR8的精确定义见源码及接手说明。整段电脑参考每次重建状态，不代表实时跨块、INT8或FPGA实现。此合同不修改现有三类HGB接口及固件发布。

## CNN-BATCH-1 ARM整段协议

冻结H27 fold0 SHA256为16d56a6b1065df35f3e11c4cc285055b421978bd451d5da1b72df8f1744fcfc7。独立候选每2秒就绪，拒绝与HGB身份混用：

```text
H,CNN-BATCH-1,READY,500,mV,<上述权重SHA256>
I,CNN-BATCH-1,<sid>,500,mV,<hp05或raw>,<total>
A,<sid>,READY,32
B,<sid>,<offset>,<count>,<CRC32八位hex>\n<连续count个little-endian float64 mV>
A,<sid>,NEXT,<累计样本数>
D,<sid>,<total>
R,<sid>,<beat_id>,<position>,<ready_at>,<status>,<class_id>,<pN>,<pS>,<pV>,<pF>
D,<sid>,<total>,<events>,<clipped>,<input_us>,<prepare_us>,<classify_us>
```

sid非零uint32，total 1—30000，count 1—32，严格逐块确认/连续offset/CRC32；不重发、不跳块。记录结束才检测、切拍、组装122形态特征及8项RR历史、FP32 CNN，最多480事件。普通传输块保持hp05状态，记录间重置所有状态。预处理及检测与冻结500Hz实现一致，CNN不使用HGB后继RR特征。

position/ready_at为500Hz零起点位置；status=0且class_id=0/1/2/3分别N/S/V/F，status=2首RR未知、4窗口不足时class_id=-1。四概率是float32位型的8位hex文本，高位在前；未知为NaN（电脑JSON转null）。F为融合拍，不是心室颤动，类别和编码均不同于HGB的VF/double协议。错误、10秒接收超时、4秒发送超时及X取消/S确认沿用整段协议约定；半包残留/物理重连恢复未验。报文无独立输出CRC，保留原始交互作复核。

三项us为板上计时：mV转换/高通/量化、检测切拍、形态背景及CNN分类，排除串口传输和等待；不是PL周期、纯CNN算子时间或端到端持续延迟。独立ARM候选不含PL推理；下述双模型候选扩展了CNN执行位置和网页入口。ECG-IN-1原QRS入口保留，但本轮未重测。

## CNN/HGB双模型PL候选（2026-11-02）

空闲身份为 `H,ECG-DUAL-1,READY,500,mV,H27-FP32,HGB-Q40`。它表示同一镜像有两个独立入口，不表示模型融合。收到 `I,CNN-BATCH-1,...` 调用H27完整FP32网络PL，收到 `I,HGB-BATCH-1,...` 调用HGB Q40树PL；每轮结束重新广播双模型身份。两端仍须核对各自固定模型SHA。网页请求参数 `board_model=true, board_classifier=cnn|hgb` 选择入口，旧请求默认hgb。

CNN也支持独立就绪头 `H,CNN-PL-1,READY,500,mV,<H27权重SHA256>`。成功结果前必须恰有一行：

```text
P,<sid>,FP32,<beats>,<mismatches>,<arm_ticks>,<pl_call_ticks>,<pl_core_ticks>,<timer_hz>,100000000
```

与HGB不同，CNN最后一个计算计数是ARM全局定时器ticks，不是PL硬件周期。`pl_core_ticks`记录启动后的轮询等待，包含轮询及起止误差；`pl_call_ticks`包含261个float32写入、启动、等待、4个logit读回。ARM同输入、同权重FP32运行完整网络，输出logit按 `abs(error)<=2e-4+2e-5*abs(ARM)` 且argmax相同验收；超差、非有限值、类别不同或超时均使会话失败。beats仅计有效拍，零拍时平均值与加速比为null。网页使用本次P计算指标，不内置演示性能值。

CNN寄存器基址 `0x43C20000`：控制 `+0x000`（start位0、done位1读清、idle位2），输出4个float32 logit从 `+0x010` 起，261个输入float32从 `+0x800` 起。输入按wave128、RR3、hand122、history8顺序；内部拼接269维后执行全连接。HGB基址仍为 `0x43C10000`，QRS外设仍为 `0x43C00000`。仅使用AXI-Lite，无DMA。ARM保留高通、检测、切拍、手工/历史特征与softmax；CNN卷积、残差、池化、RR分支和全连接在PL。整段classify_us同时包含ARM对照与PL，不能据此称整条链路提速。

N/S/V/F与N/S/VF分别保存，不自动合并、投票或将F解释为心室颤动。本节初版整段入口每段最多30000点，收齐后推理，记录间重置；后续CNN逐拍与INT8扩展见下文，HGB保留整段分析，模型融合未实现。


## CNN-STREAM-1持续输入扩展（2026-11-02）

新增模式不替换CNN-BATCH-1或HGB-BATCH-1；两个整段入口继续可用。网页默认整段，只有 `board_model=true, board_classifier=cnn, board_streaming=true` 启用流式；HGB或非板端传streaming直接拒绝。固定H27 fold0、500Hz、mV、hp05/raw、N/S/V/F、FP32及容差不变，不重训、不修改权重或PL电路。

新固件空闲头 `H,ECG-DUAL-STREAM-1,READY,500,mV,H27-FP32,HGB-Q40`；客户端确认支持流式后发送 `I,CNN-STREAM-1,<sid>,500,mV,<hp05|raw>,<limit>`，limit为1—1800000最大容量，不必事先知道最终点数。板回复 `H,CNN-STREAM-1,READY,500,mV,<固定H27权重SHA>` 和 `A,<sid>,READY,32`。B块仍为连续序号、1—32个little-endian float64 mV及CRC32；每块结束等 `A,<sid>,NEXT,<已处理点数>` 才发下一块，形成背压。输入转换/高通、检测、能量重定位、重切拍、RR和因果历史持续跨块；不对不断增长的前缀重算，不做每块重置，不等后继RR。

满足心拍条件即返回T和R，在块确认之前可出现多组；未收到结束指令也能分类：

```text
T,<sid>,<beat>,<received_through>,<arm_ticks>,<pl_call_ticks>,<pl_core_ticks>,<feature_ticks>,<arm_class_id>,<pl_class_id>
R,<sid>,<beat>,<position>,<ready_at>,<status>,<class_id>,<pN>,<pS>,<pV>,<pF>
P,<sid>,FP32,<beats>,<mismatches>,<arm_ticks累计>,<pl_call_ticks累计>,<pl_core_ticks累计>,<timer_hz>,100000000
A,<sid>,NEXT,<已处理点数>
```

R格式沿用CNN；T必须与随后R一一对应，beat连续、两侧类别相同，未知class=-1且网络耗时0；received_through为实际处理到的零起点源样本号，至少ready_at。每个有新有效分类的块返回累计P，结束再返回P。PC校验P累计与逐拍tick和及有效拍数完全一致。ARM和PL在同一拍依次运行，保留输出容差及argmax拒绝；不是并行吞吐测量。feature_ticks包含形态/背景、softmax和核对等非网络开销，不计入网络加速比。

R峰后的445点窗口需到position+266才完整；检测自身也有因果确认等待。`algorithm_wait_ms=(received_through-position)*2` 是算法可用数据等待，不是网络耗时。CNN网络均值/累计从ticks÷timer_hz得到；累计倍数为ΣARM_ticks÷ΣPL_call_ticks，FPGA调用包含261float写、启动/轮询及4logit读取，计算等待仍是ARM计时而非PL硬件cycle。网页“收样至结果”以同一PC单调时钟测量received_through样本进入本地队列至收到R，包含队列/UART/检测/ARM+PL/回传；不包含之前窗口等待、ADS到PC无线时间或浏览器绘制，不是单独ARM或PL端到端延迟。两者不要相加后称精准器件延迟。尚无电脑CPU网络实测，不显示估算数。

正常完成或用户停止先停来源、送完已保留队列，再 `D,<sid>,<实际已确认点数>`，板flush将尾部不足窗输出status4，不补零/插值，返回最终P与原CNN D完成报文。停止保留已有有效结果，reason=stopped_by_user；错误/CRC/坏序号/超时失败，不称成功，不自动续接。来源5秒无新字节视为故障，新连接须新会话；正常串口块仍延续状态。队列4096点，实时来源积压满直接报错、不偷偷丢点；回放来源允许背压。源无每样本序号/CRC，不能证明无线无丢样。

输入环形缓存4096、有限待处理32、背景8及RR历史均有界，无malloc；固件单会话上限1小时仍需长时实测。网页显示4096点/256事件，完整输入和逐拍结果保留文件。自动电脑HGB分析另受200000点上限，不把超限记录截短后分析。

## 动态 W8A8 三核协议（2026-11-03已完成对应JTAG板测）

对应匹配交付为 `board/cnn_fast_20261103/`，整段及流式实测见 `docs/evidence/cnn_int8_fast_20261103/summary.json`；以下报文格式保留，不将该JTAG证据扩大为新版QSPI启动验收。

三核身份：`H,ECG-TRIPLE-1,READY,500,mV,H27-FP32,H27-W8A8,HGB-Q40`。原 CNN-BATCH-1、CNN-STREAM-1、HGB 请求保留。量化请求仅将 CNN 请求名换为 `CNN-INT8-BATCH-1` 或 `CNN-INT8-STREAM-1`，其余样本/CRC/背压合同不变；PC选择 W8A8 必须先见三核身份，否则不送样。

P 报文精度为 W8A8；T/R 格式不变，输出对应 INT8 分类。每次 P 后新增：

```text
Q,<sid>,<valid_beats>,<fp32_vs_int8_class_changes>,<fp32_arm_ticks>,<fp32_pl_call_ticks>,<int8_arm_ticks>,<int8_pl_call_ticks>,<timer_hz>
```

共9字段。每项为同一批有效心拍的累计值，零拍时计时全零；PC要求拍数、timer_hz及INT8时间与P完全相同，流式不允许计数倒退。整段可先 P/Q 后 R，完成时检查有效拍数；实时每块累计 P/Q，结束再发最终 P/Q/D。四种计算依次执行，不是同时四路推理；FP32和INT8各自必须通过同精度 ARM/PL logit容差与argmax检查才发成功结果。跨精度类别变化是量化差异，不作为硬件 mismatch。feature_ticks已排除四种网络时间。

权重/激活范围[-127,127]，最近舍入、半值远离零，二次幂scale；权重每输出通道，激活每层每拍动态scale。MAC为INT32，最大累加界4,338,701；残差、缩放、偏置、归一化和输出为FP32。量化参数身份见导出export.json与构建manifest，原FP32模型SHA保持，不能只凭该SHA声称INT8参数相同。资源API与会话计时独立，无布局布线证据返回pending，不生成虚假占用。
