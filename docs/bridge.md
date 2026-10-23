# 电脑双向中转使用说明



相关文件按同一功能命名：电脑入口`src/pc/ecg_bridge.py`，配套模块`ecg_bridge_core.py`、`ecg_bridge_protocol.py`、`ecg_bridge_capture.py`、`ecg_bridge_serial.py`；板端目录`src/ps/ecg_bridge/`，构建入口`board/build_ecg_bridge.py`，离线测试`sim/test_ecg_bridge.py`及其C适配`sim/ecg_bridge_host.c`。本文讲操作，[bridge_protocol.md](bridge_protocol.md)讲输入协议；结果协议仍单独见`uart_protocol.md`。



中转路线和字段见[ECG-IN-1](bridge_protocol.md)，板端结果见[ECG-UART-1](uart_protocol.md)。主窗口“送样 / 双向中转…”接入厂商CSV或蓝牙采集及Zynq收发，操作见下节；独立命令行入口src/pc/ecg_bridge.py保留。界面功能与软件闭环不代表已经通过真实蓝牙/USB_UART/PL联调。



## 界面送样



1. 先在Vitis运行匹配500Hz硬件的ecg_bridge，启动配置ecg_bridge_app_hw_1；不能用ecg_stream代替。板端在输入I报文之前可以没有输出，等待输入不代表卡死。关闭Vitis串口终端和其他占用COM的软件。

2. 启动python -B src/ui/main.py，点击“送样 / 双向中转…”。打开时主窗口只收会先停止保存，独立采集窗口与中转窗口互斥，避免抢占串口。旧src/pc/ecg_monitor.py无参数启动仍兼容。

3. 点击“识别端口”，选择Zynq USB_UART；如用蓝牙，再选不同的采集USB接收器。设备按USB实例而非固定COM号匹配，连接前复核；多个CH340候选不能仅凭芯片名判定用途，首次需要手选。收到匹配的结果会话后记住Zynq身份，不发送识别探测命令、不自动重连或复位。

4. 第一轮点击“厂商CSV → Zynq…”，选择五列RawData原文件，不选HeatData或旧CLI的int16 CSV。按500Hz软件时间回放全文件，CH2减8388608、默认算术右移8位并饱和；转换/削顶和完整原件分别保留。已有int16 CSV继续走CLI。

5. CSV通过后再用“蓝牙采集 → Zynq”，本轮点数默认5000，可改为1..1800000。先确认无线端正在输出；READY后才打开采集口，起始按连续三帧候选锁定，锁定后错误即停止。板端激活后的无输入超时仍为5秒；不增加自动重传/自动复位。

6. 上图区分来源24位有符号原码，下图显示提交后回传的int16值及黄色板端事件标记；不同单位不混画同一幅值轴。两图按源index从0建立500Hz逻辑时间；CSV原时间保存在capture/samples.csv，并记录csv_first_time_s。映射为source_index=upload_seq=result_index，CSV时间=csv_first_time_s+index/500；USB到达时间不充当采样时间。

7. 自动结束需done=true、上传/确认/回传计数相等、逐值回传一致、事件序号/RR一致、无已知丢弃、完整END和DONE且文件/连接关闭成功。蓝牙原帧无源序号/CRC，源丢样始终未知；事件数量/准确率不能预设。滤波和分类仍未实现，不填入厂商或电脑计算值冒充板端结果。

8. “停止并保存”停止来源后，排空已记录待送数据并等待有限确认收尾；界面标正在收尾，仍可响应。手动停止即使收到DONE也记录stopped_by_user，不能冒充全文件完成。关闭窗口也等待后台释放连接。遇确认超时/坏帧/驱动/队列/记录错误停止留证；重跑前须先重新Run板端并重新配置PL，不能把新源拼到旧会话。



记录新建于tmp/pc_bridge_logs/，不覆盖旧目录：capture/保存来源原文、两通道及转换预览；results/仅保存H/W/E/T/L及CSV；根目录upload.log/usb_rx.log/controls.log/normalized.csv及summary.json记录输入、确认和总状态。CSV滤波列只保存为厂商历史结果，不上传。合计数据限额64MiB，分配来源和中转各32MiB，任一达到即停止；少量摘要另计。GUI上游队列2048点、BridgeClient队列4096点、一包最多32点，显示缓存有界，不静默丢点；满队列失败不等于无线源本身无丢失。



本机当前工作区为tmp/ecg_bridge_clock/vitis_workspace，包含计时宏修复；ELF SHA256为e5b18e40c927d4663d33af68b4ccdfa391044e315ed69c81354971a2d5b61c24。旧tmp/ecg_bridge_final/vitis_workspace保留首轮CLOCK_REVERSED失败对应版本，不再作为运行入口。两者均不同于脚本默认新建路径tmp/ecg_bridge/vitis_workspace，不要为复跑移动活动工作区或改写旧工程；修复/上板证据见[验收记录](records/bridge_board_20261020.md)。操作可参照[客户端说明](pc_monitor.md#界面双向中转)。



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



默认新工作区为tmp/ecg_bridge/vitis_workspace，组件为ecg_platform和ecg_bridge，启动配置ecg_bridge_app_hw_1。已有目录即停止；可在当前终端设置ECG_STREAM_WORKSPACE为新的英文路径。硬件默认releases/latest/bridge/hardware；自定义XSA时必须同时指定匹配的ECG_STREAM_BIT/ECG_STREAM_PSINIT，不能使用latest的360Hz组合。



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

python -B src/pc/ecg_bridge.py --vendor-log '<厂商原文.bin>' --format document_34 --channel 2 --shift 8 --aligned --source REPLAY --rate 500 --zynq-port COM14 --output-dir tmp/bridge_vendor_new

```



当前用户确认34字节，厂商软件与CSV核对CH2为ECG；shift=8仍不是最终标定或检测输入合同。程序先保留两个24位通道，再按指定通道算术右移并饱和至int16，计削顶；不会根据波形猜通道。当前显式使用document_34，不自动识别或混用旧source_10。--aligned表示调用者已确认初始边界；若无法确认，不应使用该开关伪造条件。数据内可能出现AA BB，格式合法仍不能证明无误码。



只有确认蓝牙提供串口透传虚拟COM之后，才能用实时采集分支；任意BLE设备不能直接套用：



```powershell

python -B src/pc/ecg_bridge.py --vendor-port COM20 --format document_34 --channel 2 --shift 8 --aligned --samples 5003 --source ADC --rate 500 --zynq-port COM14 --output-dir tmp/bridge_live_new

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



查看CLI回传波形时启动PC监视器，选择“打开日志回放”，打开本次results/raw.log；CLI原始24位采集码保存在adc.csv，GUI版本保存在capture/samples.csv。结果W为提交Zynq的16位码，不能混为同一幅值单位。**有限CSV/受控脉冲的PS→PL→USB_UART双向数字回放已上板核验，真实蓝牙与人工GUI仍待验，有限120秒数字负载已单独核验。** 原始CSV默认右移8位下无事件，与参考一致不代表检测效果合格；详细边界见验收记录。



## 当前发布与重复运行



匹配500Hz bridge已加入[系统交付](../releases/latest/README.md)，预编译程序在bridge/prebuilt、成对硬件在bridge/hardware，360Hz smoke独立保留。包内bridge/board/run_bridge.ps1先做CheckOnly，再显式指定CableSerial启动；不要把旧ecg_bridge_final计时失败版当当前版本。当前工作区tmp/ecg_bridge_clock/vitis_workspace原位保留，运行配置ecg_bridge_app_hw_1。新候选构建默认从latest/bridge/hardware读取匹配组合，启动模板从latest/smoke读取并替换应用名。文件迁移/便携入口只完成离线验收，不新增板卡成绩。



有限持续与CRC/超时拒绝及明确JTAG恢复见两轮记录；发布归档/清单/复制后回放见发布记录。无标注真实CSV的零事件问题仍待冻结幅值及初始化方案，不以通信验收代替检测准确率。



## 启动学习候选与原版分开运行

原版ecg_bridge/QRS-ORIG-60仍为已验数字通信交付；独立ecg_auto/QRS-AUTOPEAK-60用于启动学习/峰判决候选。两者共用相同输入/结果格式，但必须选择各自匹配bit/XSA/ps7_init/ELF和运行配置，不能只换ELF。电脑请用正式源码客户端，已验发布内旧客户端不接受候选身份。候选工作区、两秒预热及额外3拍内部计算见[候选说明](qrs_auto.md)，真实上板和准确性不能继承原版证据。
