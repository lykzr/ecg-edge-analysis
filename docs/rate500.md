# 500Hz处理与验证

## 适用输入

新ecg_runtime500应用接收连续500Hz、4096单位/mV、int16的标准数字样本，序号从0开始；不能直接发送厂商34字节帧或右移预览码。ADS1292R→STM32及厂商蓝牙协议保持原样，在电脑端先解码并依据明确的幅值合同换算；这项实采换算/标定仍需采集负责人确认。采集端不需要迁就360Hz。

500Hz是源采样率。内部有理FIR为18/25，1001抽头Kaiser8.6，固定群延迟20个360Hz内部点；事件回到源编号使用`round((internal_position-20)*25/18)`，不是拟合标注时间偏移。上报确认时刻为实际收到的500Hz源序号。RR为相邻源位置之差，心率为`30000/RR`次每分钟；首RR未知。保留完整原码与源序号；蓝牙到达时间不当采样时间。

独立500分支为量化后相邻点复核增加梯度佐证及窄尖刺保护，并把主检测和后续等待重新分配以补偿转换延迟。原360Hz父本、原验收门槛不变；不声称500分支只是无行为变化的原版移植，也不声称所有信号定位误差最多1点。

模型128点波形直接从500Hz源波形按原协议切取178+267点，再36/125重采样到144Hz、共同时间网格插值及逐拍标准化；RR也由500Hz源历史生成。首次或尾部不足明确无效，不补零、不拿专家位置补拍。最终权重/INT8尺度仍待模型负责人交付。

## 构建

在项目根，用现有Vitis环境执行，安装路径自行替换：

```powershell
$env:ECG_RUNTIME_RATE='500'
$env:ECG_RUNTIME_WORKSPACE=(Join-Path $PWD 'tmp/runtime500_new')
& '<Vitis>/bin/vitis.bat' -s (Join-Path $PWD 'board/build_runtime.py')
```

输出目录必须不存在，建议短路径。默认复用已验smoke的匹配bit/XSA/ps7_init，不改PS7/MIO/DDR；ARM运行时不使用旧PL检测器。组件名为ecg_runtime500，build_manifest.json保留本轮源、硬件、ELF、链接图和SHA。设置500后不要拿该环境变量去构建预期360的工程；360构建前显式设回360。构建不是上板验收，JTAG/Flash授权与硬件身份另核。

## 电脑入口与分段协议

在客户端“送样/双向中转”窗口选择“500Hz标准CSV → 新QRS”，标准CSV头为`index,sample,fs,scale`，每行fs=500、scale=4096。也可以调用RuntimeWorker(..., sampling_hz=500)。500Hz源波形横轴以index/500显示，内部360Hz编号不用于显示或返回RR。

客户端profile=runtime500；只接受启动身份`ps-runtime500-ready/QRS26-500-ARM/500/4096/0xD`，就绪后发送`I,ECG-IN-1,<session>,500,<REPLAY或SYNTH>,4096`及原CRC32。D/F/A语法与原ECG-IN-1相同；收到会话H及READY才送D，一包在途。波形W仍回传500Hz源输入，滤波列NA；E位置/RR为源采样号，类别?/置信度-1。分类未交付时NO_MODEL。旧runtime360与旧厂商legacy500合同独立，错率、错scale、CRC、缺号明确拒绝，不自动猜测。

厂商CSV/蓝牙旧按钮仍对应旧ecg_bridge与scale=-1，不能因为都是500Hz而混用新应用。新标准CSV入口只证明单位明确的数字输入可运行；实际厂商原码到物理量换算、无线/双USB/拔插仍待实物验证。

## 复现与证据

运行已有QRS解释器的sim/test_pipeline500.py检查实际C窗口、RR、内存、前缀因果和UART/PC闭环；系数由build/generate_rate500.py与build/generate_window500.py用现有SciPy复核。正式表已保存，裸机构建无需SciPy。

完整配对使用data/benchmark_rate500.py，显式给出raw、golden、exe、out；golden可用冻结data/benchmark_qrs_runtime.py以rate360从官方数据重建，不能要求协作者具有作者历史tmp。全部42条均为已知开发记录；500Hz输入由它们离线构造，不是未触碰患者、真实500Hz临床或实采测试。原门槛及最终逐记录结果见data/rate500_protocol.json、data/results/rate500_20261024.json和[实验记录](records/rate500_20261024.md)。
