# PS流式应用

## 用途与输入

ecg_stream是独立裸机候选应用，用于把受控数字输入、现有PL检测事件和PC协议接收连接起来。它不替换已通过的ecg_smoke或releases/latest；构建/主机检查/上板分别以[当前500Hz记录](records/stream_500_20261019.md)（[旧360Hz记录](records/ps_stream_20261018.md)保留历史）为准。

输入明确声明SYNTH：先100个零，再每500点一个正负交替的±20000单点脉冲，其余为0。默认5003点，约10.006秒名义输入时长，末批3点不补齐。原始码值未标定，scale=-1；filt=NA、类别?、分数-1。这不是生理ECG波形、真实AFE采集、CNN或准确率测试。事件来自实际PL FIFO，检测器版本QRS-ORIG-60，位置不是精确R峰。

## 构建独立工作区

默认使用独立500Hz硬件（不能混用latest的360Hz镜像）。先从项目根目录运行已有Vivado，安装路径按本机替换：

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/stream_500.tcl
```

该步骤在新的`tmp/ecg_stream_500/`生成500Hz硬件及匹配XSA/bit/ps7_init；目录存在即停止，不改共享360Hz工程或已验收smoke发布。硬件构建完成后再用Vitis构建PS应用：

```powershell
& '<Vitis安装目录>/bin/vitis.bat' -s board/build_ecg_stream.py
```

默认新建`tmp/ecg_stream_500/vitis_workspace`，包含ecg_platform和ecg_stream。目标已存在即拒绝覆盖；重建时只对当前终端设置新路径：

```powershell
$env:ECG_STREAM_WORKSPACE = '<项目绝对路径>/tmp/ecg_stream_run2/vitis_workspace'
$env:ECG_STREAM_SAMPLES = '5003'
& '<Vitis安装目录>/bin/vitis.bat' -s board/build_ecg_stream.py
```

样本数允许1..1800000；最多一小时是本程序整数预算限制，不是已经通过一小时验收。工作区路径使用无空格英文路径。默认从tmp/ecg_stream_500/hardware读取匹配XSA/bit/ps7_init，构建后复制到新组件内，不改原文件。自定义XSA时必须同时提供ECG_STREAM_BIT、ECG_STREAM_PSINIT，调用者另核对三者确实同源；仅有哈希不证明任意输入文件彼此匹配。

构建脚本使用Vitis自带Python API，普通Python不可直接替代。仅在所有源码副本及ELF核对成功后生成build_manifest.json，包含源/硬件/ELF哈希与参数。不生成该清单或未输出ECG_STREAM_BUILD_PASS即不能认定构建完成。若服务启动报本机回环连接权限错误，按执行环境申请运行权限；不改安装目录ACL或以管理员权限作为默认方案。

## Vitis与PC联调步骤（待实物验收）

1. 按[下载教程](download_guide.md)核对领航者V2、供电、JTAG启动与USB_UART，硬件参数不从其他板卡复制。
2. Vitis的Set Workspace选择这次新工作区，左侧选择ecg_stream。不要打开旧smoke工作区后运行错应用。
3. 先运行[PC监视器](pc_monitor.md)，填写实际COM口、115200/8N1/无流控并连接记录。Vitis串口终端等其他软件须关闭，避免占用。无需先有H就能开始原文记录。
4. 在Vitis左侧FLOW选择ecg_stream并Run，使用`ecg_stream_app_hw_1`。生成的启动副本启用系统复位和重新配置PL；**每次重跑都必须保留这些选项**，因为硬件无检测器软件复位与样本计数读取寄存器。
5. 保存完整原文、CSV和摘要；既要核对最终END，也要核对T的丢弃数、PC坏行/缺口及完整样本/事件。没有END或任何错误不能当完整运行通过。需要重跑时，PC先停止保存并建立新记录，再在Vitis重新Run。

普通完整输入的预期检查项（不是实测报告）：5003个样本；10个事件；事件号1..10；位置70+500*i（i=0..9）；RR首个0、其余500；无源丢样、发送丢样或FIFO丢事件；无解析错误、波形/事件缺口；结尾为reason=completed。位置由500Hz参数的RTL合成向量仿真核对，原smoke仍保持360Hz，不能用于宣称ECG定位精度。板端输出包含同一H每秒重发，用于中途连接获得元数据；首批前/末尾数据完整性仍须结合总量核对。

## 调度、发送与异常

- 使用XTime全局计时器，不清零计数器、不改变PS时钟/分频，只使能计数。第i个样本的截止为`start+floor((i+1)*timer_hz/500)`，避免整数周期累积误差；不以UART发送速度推进样本。
- 单线程轮询，每次最多提交一个到期样本、消费8个事件、发送32个就绪字节；UART满时立即返回，不等待整行发完。8KiB环形发送缓冲在内存中，完整报文原子入队。没有采样中断或UART发送中断；严格节拍、格式化/MMIO成本与最坏时延必须在板上测量。
- W每8点打包，预留1KiB给事件/控制行。队列压力下丢整批W，仍向PL送样并推进原序号，累计tx_sample_drop。事件/控制行无法入队则报错停采；FIFO队首先完整读入并成功排队，再弹出，不将seq/pos为0当空。
- FIFO事件丢弃读0x20；source_sample_drop=0仅表示本合成源不跳过计划中已提交段。错过一个完整周期时停止，不追赶突发、不继续压紧源序号；尚未执行的后续计划样本不是成功采集。真实ADC丢样统计未实现。
- 状态每秒输出，未知心率/分类为未知，不把旧值当当前值；不监测的状态用NA。END带总提交样本、已排队事件、发送样本丢弃、队列峰值、最大观察迟到ticks及计时器频率。该迟到值在调度入口观测，不等于示波器测得的实际采样抖动。
- 输入结束后保留至少1ms的候选尾部观察，再发末批；排空软件队列后输出最终T/END，最后有界等待物理UART空闲。UART连续2秒无法推进则退出，可能无法送出最后错误行，应结合调试器中的ecg_stream_result和缺失结尾定位；不自动复位抹掉现场。
- session由本次构建随机ID与启动计时器组成，同一H不变。它不是持久启动计数器，不能保证所有复位情形下全局唯一；每次重新启动必须在PC新建记录。此限制仍属B08待验项，不跨未知重启拼接记录。
- 不接收START/STOP/GET_STATUS命令，能力位只声明RAW_W/EVENT_E/STATUS_T（0xD），不声明命令、滤波或分类能力。PC停止记录不会停止PS送样；当前是有限长度试验程序，断连后不会自动停流。

reason=completed只表示计划输入执行结束，不自动表示零丢弃或真实链路通过；慢速发送可正常结束但出现TX_DROP。最终连续时长/峰值负载和通过门槛应在B11测试前冻结。

## 主机检查

```powershell
python -B -m unittest discover -s sim -p test_ps_stream.py -v
```

需要已有GCC，可用ECG_HOST_CC指定编译器；不自动安装。测试编译实际stream.c，使用假时钟/寄存器/FIFO/UART，并用现有PC解析器检查输出。假FIFO提供已知事件，不能证明真实检测器、AXI MMIO、UART驱动或物理节拍正确。原smoke仍作为独立硬件回归。

## 采样率版本边界

当前候选为500Hz、120ms积分窗（60点）、200ms不应期（100点），H/T声明500、算法标识QRS-ORIG-60。初始化会读取PL的0x24寄存器，不匹配即CONFIG_MISMATCH且不送样；不能只修改会话fs或拿旧360Hz bit继续运行。心率按`60*fs/RR`换算，合成脉冲每500点一次，名义60次/分。

此版本未上板；旧360Hz工作区/历史证据仍保留，但不对应当前默认源码。真实ADS1292R的DRDY节拍、通道、幅值缩放与滤波仍待核实；模型144Hz输入及公开数据原始采样率不随本候选改动。[本轮记录](records/stream_500_20261019.md)区分主机、RTL、构建和板上阶段。
