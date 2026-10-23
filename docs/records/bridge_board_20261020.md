# 双向数字回放上板及计时修复

2026-10-20用户说明Zynq一直连接并授权直接更新。本轮通过命令行JTAG临时配置既有匹配500Hz硬件和bridge程序，验证电脑→USB_UART→PS→AXI→原PL检测器→FIFO→电脑；未写Flash，不替换smoke发布。真实无线、人工GUI、持续负载及检测准确率分别保留待验。

## 首轮失败与定位

旧ELF为tmp/ecg_bridge_final/vitis_workspace/ecg_bridge/build/ecg_bridge.elf，294076字节，SHA256为049fceb91c6d29a02747e68bc163668c03ac4947d9184e76e4cd6c53cbc124b5。加载后电脑发送I初始化，没有收到任何字节，2秒等待确认超时，0样本上传；记录保留tmp/checkout_board_20261020/board_csv_01/。

先保存故障现场再暂停核0读取：ecg_bridge_result=-5，PC停在_exit，bridge.failed=1，error指针指向ELF中的CLOCK_REVERSED。没有通过复位、清接收缓存或重传掩盖错误。一次批量读UART覆盖FIFO时被调试器的read-once保护拒绝，未强制读取；随后仅读非破坏性状态，见diagnose_registers.log。UART后来的OVER/RXFULL不能当作首因，因为程序已因时钟倒退退出，后发I尚留在FIFO。

BSP的xtimer_config.h定义XSLEEPTIMER_FREQ为XPAR_CPU_CORE_CLOCK_FREQ_HZ/2，COUNTS_PER_SECOND转引该宏；CPU频率为666666687Hz。旧式elapsed/COUNTS_PER_SECOND和elapsed%COUNTS_PER_SECOND因展开无括号，分别变成elapsed/CPU_FREQ/2、elapsed%CPU_FREQ/2；约2秒边界余数归零，微秒值从约250000回落，触发CLOCK_REVERSED。

修复main.c：先将(uint64_t)(COUNTS_PER_SECOND)求值为timer_frequency，再由bridge_time.h纯函数按商/余数转微秒。发送排空的2秒界限也使用该常量；不改PS时钟、预分频、MIO、UART速率、AXI或PL。新增使用同样无括号宏的C回归，覆盖2秒边界、分钟/小时/一天，19项中转核心测试通过。此前18项只测bridge.c和假时钟，未覆盖PS适配层的宏展开，不能推导实际XTime换算正确。

## 新构建和目标

| 项目 | 已核对内容 |
| --- | --- |
| 工作区 | tmp/ecg_bridge_clock/vitis_workspace；旧final工作区/ELF保留，不原地覆盖 |
| 应用/配置 | ecg_bridge / ecg_bridge_app_hw_1，系统复位、Program Device和ps7_init |
| 新ELF | 294364字节；SHA256 e5b18e40c927d4663d33af68b4ccdfa391044e315ed69c81354971a2d5b61c24 |
| 源码 | main.c、bridge.c、bridge.h、bridge_time.h与导入副本及build_manifest.json逐项一致 |
| 硬件 | 原500Hz bit/XSA/ps7_init不变，哈希与原manifest一致；PL读回fs=500、window_ms=120、refractory_ms=200 |
| JTAG | 唯一xc7z020，Digilent JTAG-HS1，序列号210512180081；启动模式寄存器为0（JTAG） |
| USB_UART | COM23，CH340，USB实例VID_1A86&PID_7523/6&1ef5fd6f&0&2；115200/8N1/无流控，测试后关闭 |

本地套接字在沙箱内被拒绝；通过正式权限流程访问本机硬件服务后识别目标。没有通过换工具绕过拒绝，也没有修改权限/安装目录。构建、JTAG和诊断输出保留tmp/checkout_board_20261020/。构建清单的scope记录构建时事实，不回写为上板通过；下列验收独立记录。

## 两组实际收发

| 用例 | 结果 | 边界 |
| --- | --- | --- |
| 厂商CSV→GUI中转后台→实板 | 全10412点，上传=确认=回传，逐值等于(CH2-8388608)>>8；原CSV字节/SHA一致、削顶0；END/DONE正常 | 使用BridgeWorker后台，不是人工点击/观察GUI；原始CSV的厂商滤波列未上传 |
| 受控数字脉冲→CLI→实板 | 全5003点逐值回传；10事件，号1..10，位置70+500*i，首RR=0、其余500；END/DONE正常 | 输入声明SYNTH；快速回放不是500Hz物理调度性能试验，位置不冒充精确R峰 |

两组均无解析错误、波形/事件序号缺口、FIFO事件丢弃或发送丢弃；上游source_drop仍未知，不改成0。每个用例前重新配置PL/系统，未拼接会话。CSV约20.94秒墙钟包含电脑回放/收发/保存，不是FPGA推理性能；来源队列峰值9、BridgeClient峰值39只对应本次CSV。CSV与脉冲的结果日志各回放一次，raw/samples/events/status/sessions五文件均逐字节一致。逐项核验与哈希见tmp/checkout_board_20261020/board_verification.json，原目录board_csv_02/、board_synth_01/保留全部输入/上传/接收/CSV。

**真实CSV在本次默认右移8位、未加滤波的输入设置下事件数为0，原检测器整数参考也为0。** 这只说明实现一致，不能算心电检出率合格，也不能把无事件解释为正常。当前int16值范围2072..2459，后续需以明确的输入合同核对滤波/工频、DC/幅值处理与检测器参数，再用标注或适用人工依据验算法效果，不为产生事件盲目改缩放或阈值。

程序摘要中的board_validated=false为客户端静态默认声明，本轮保留原字节；物理验收依据本记录、JTAG目标及独立verification.json，不手改原始摘要冒充程序自动认证。

## 精选原始证据

以下是USB_UART接收原文，包含ECG-IN-1的A确认以及ECG-UART-1结果；不能直接当纯结果日志喂入旧Monitor。界面回放请使用原目录results/raw.log。

| 原文 | 字节数 | SHA256 |
| --- | --- | --- |
| [CSV完整接收](uart_bridge_csv_20261020_pass.log) | 119246 | f131a14c955230454d6600c59a21462ff4b14a7dc2184f6d982f39b8d31bf2b2 |
| [脉冲完整接收](uart_bridge_synth_20261020_pass.log) | 42173 | c8e1a8741a1a0643150a36a6a1f8c0fb1d12aabb071e4aca0d9d75f97132b702 |

## 文档与跨平台修复

主体计划保留360Hz/8项历史，并明确当前合成候选500Hz/eb73eda2…；更新PC/PS已有基础和360Hz演示与500Hz板端的区别。只修sim/check_checkout.py的清单分隔符解析，data/baseline/files.json及29份基线文件字节/哈希不变；绝对路径、盘符和逃逸目录仍拒绝。四项新增检查覆盖POSIX路径拆分及边界，但没有在Linux/macOS原生环境复跑，不冒称VM验收。

本轮Windows最终回归：路径4、PC中转14、采集20、串口16、PC核心14、中转核心19、ADS14、PS合成流9，共110项，无跳过。正式记录追加lykzr.md，计划只勾选受控数字回放子项；B08/B09/B10/B11整项、真实无线/持续负载、人工GUI/高DPI、ECG算法效果、滤波/CNN/INT8仍未完成。模型训练未恢复，根README/资料索引/latest不改，Git持续暂停。
