# 使用、下载与重建

## 队友只拿Git时，从这里开始

先读[交接任务](../report/handoff.md)。正式源码、三份HGB权重、192特征代码、常量、合成输入/黄金结果、ARM实现、PL现有源码、构建脚本、许可和精选实板证据都随Git。必要入口列在[接手依赖表](../model/handoff_requirements.json)，不是让队友另外索取作者的tmp。**完整分类PL尚待开发；原HGB训练来源也未完整交付，不能称这些已经完成。**

拿到仓库后，先不连板，执行：

```powershell
python -B sim/check_repository.py
python -B sim/check_checkout.py
python -B sim/check_system_release.py
python -B sim/check_git_handoff.py
```

前三项用标准库。最后一项核对固定模型文件及继续开发所需入口，不训练、不访问患者、不要求本机旧路径。需要完整HGB自检时，安装下面列出的模型依赖再运行。新成员的安装由本人在自己的环境执行；这些命令不会在本文维护时自动安装。

### Git不带的东西：到哪里获取

| 内容 | 获取方法与核对内容 |
| --- | --- |
| Python、Node/npm | Python从 https://www.python.org/downloads/windows/ 获取；网页已验Python3.14、Node24，Node从 https://nodejs.org/ 获取。网页锁文件为src/web/requirements-lock.txt；前端package-lock.json由build/build_web.ps1使用npm ci安装。缓存和环境由脚本生成到tmp，不需要队友复制作者环境。 |
| HGB模型Python依赖 | 优先使用Python3.12独立环境，依赖以model/inference/requirements.txt为准；网页另配ECG_HGB_PYTHON，不降级系统Python。依赖从各包官方发行渠道安装。当前Windows x64原生参考程序已带源码和二进制，首次推理不需要训练库。 |
| Vivado/Vitis、ARM GCC与主机GCC | 从 https://www.xilinx.com/support/download.html 的AMD官方入口获取2026.1及适用许可，安装Zynq-7000和裸机组件。ARM GCC使用匹配Vitis安装中的arm-none-eabi-gcc，并同时提供ar/nm/size；路径通过ECG_ARM_GCC指定。主机C对照需已有GCC，Windows可从 https://www.msys2.org/ 获取MinGW-w64，显式传--cc，不把编译器复制进Git。 |
| 领航者V2原理图/指南/官方例程 | 从 https://www.alientek.com/ 官方产品/资料入口按“领航者V2 ZYNQ”查找，或向购买渠道索取对应修订资料盘；核对实物底板/核心板修订和Zynq-7020。所需资料为对应原理图、FPGA开发指南、嵌入式Vitis指南；本机曾参考FPGA指南V3.4、Vitis指南V1.2，不能据此替代修订核对。官方资料只读，示例另复制到tmp英文路径构建，不上传整盘。 |
| ADS1292R/STM32/JDY-18资料 | 向实际模块卖家索取匹配PCB修订原理图、实际烧录固件/版本、34字节协议、供电/电平及VREF/PGA依据；芯片资料取 https://www.ti.com/product/ADS1292R 。仓库docs/protocols.md已有当前解析定义，但不能代替板上固件或电气核验；10字节旧源码不能当34字节固件。 |
| ECG公开数据 | MIT-BIH https://physionet.org/content/mitdb/1.0.0/ 、INCART https://physionet.org/content/incartdb/1.0.0/ 、SVDB https://physionet.org/content/svdb/1.0.0/ 、NSTDB https://physionet.org/content/nstdb/1.0.0/ 。各自阅读许可并按官方SHA核对；已有下载入口见data/README.md、model/prepare/download_external_ecg.py。只按当前批准协议下载/使用需要的记录，数据留tmp；不要把CNN协议当HGB原训练协议，也不要为接线开发开封独立患者。LTDB/LUDB仅在实际任务需要时按third_party.md列出的来源获取。 |
| 竞赛指南/报名与通知 | 从赛道主办方 https://www.fpgachina.cn/ 与 https://www.anlogic.com/ 官方竞赛入口取得当前指南和通知；核对AMD自主选题3.3.3—3.3.5及实际报名组别/平台要求。采用截止仍需提交前核实；不把本地旧PDF上传代替官方来源。 |
| 本人采集数据、账号和串口号 | 新成员自行采集或向数据本人申请授权；数据库、密码、.env、测量原件不上传。COM号/JTAG序列号按本机实物识别，不能照抄旧日志。无设备时可用随Git合成样例继续模型/PL开发，不报告真实采集已验。 |
| 原始AI聊天记录 | 由各成员从自己使用的平台导出原始提示/回答/纠错，先经所有者同意并脱敏，再把允许提交的片段写入report中的英文命名文件。现有skill不是原始聊天替代物；Git开发不依赖私人聊天，不能编造原文补缺口。 |

### 跑当前模型、导出给FPGA使用的参数

```powershell
py -3.12 -m venv tmp/model_env
& ./tmp/model_env/Scripts/python.exe -m pip install -r model/inference/requirements.txt
& ./tmp/model_env/Scripts/python.exe -X utf8 -B model/inference/check.py
& ./tmp/model_env/Scripts/python.exe -X utf8 -B model/inference/run.py --input model/inference/examples/synthetic500.csv --fold 0 --preprocess hp05 --output tmp/first_beats.csv --features tmp/first_features.npz
& ./tmp/model_env/Scripts/python.exe -X utf8 -B build/export_hgb.py --output tmp/first_parameters
```

输出必须使用新名字。导出器从Git内v92/fold0权重生成192棵树及常量C文件，无训练、无旧缓存。软件参考入口是model/inference/ecg_model，ARM参考在src/ps/ecg_hgb；输入和返回字段见docs/protocols.md。用同一合成记录和特征黄金结果开发PL，先验证结果再计时；double树不能直接声称INT8。主机完整C对照可执行`python -B sim/check_hgb_arm.py --output tmp/host_hgb_new --cc <已有主机gcc.exe>`。

### 新ARM候选与旧latest必须分开

releases/latest是已发布的旧runtime500版，不含新双协议HGB应用；不能把旧BOOT.BIN当新版。**重建新版不需要原作者Vitis缓存**：使用本页“使用板载ARM模型”的构建命令，从Git内smoke的匹配XSA/bit/init、正式HGB/legacy源码和导出权重生成新Vitis工程、FSBL/ELF，再生成候选BOOT.BIN。构建和打包不操作实物。已有双协议构建身份、源码/镜像SHA、启动实测输出保留在docs/evidence/hgb_web_board_20261101.json，可对照而非伪造新板已验。编译器/环境不同可能不逐字节相同，须保留新清单并重新验证，不修改原证据强行配合。下载或Flash覆盖由实际操作者另行授权。

### 目前确实没有的原始HGB材料

向原feature/ecg-model分支负责人索取：对应v92的训练/标签生成/原评价脚本，精确依赖与随机种子，数据版本/记录清单/患者划分/缓存哈希，N/S完整原始标注映射，原患者支持数下限，权重导出与选择依据。交接时逐项与model/inference/provenance.json、integration_profile.json及权重SHA核对；不要索取整套虚拟环境或所有患者波形，也不要运行旧CNN脚本冒充HGB复训。收到后将许可允许的代码/配置纳入model，原始波形仍走合法获取入口。

这些材料本机尚未找到，**不能承诺队友只拿Git就能复训原HGB或重建全部历史评分**。它们不阻止运行现有固定权重、改界面、开发PL和做软件数值比较；阻止的是原训练复现、完整标签解释和相关验收证明。若负责人拿不出，保留缺项，不推测标签、不伪造来源；新建训练路线需另外授权并保留新版本身份。

## 环境与接线

使用 Windows、Python 3.14、Node 24；板端重建使用 Vivado/Vitis 2026.1 及 Zynq 裸机工具。示例中的 <Vitis>、<Vivado>、Python路径、串口和下载器序列号均填写实际值。所有命令从项目根执行，生成内容放 tmp/；发布运行不依赖作者历史工具工作区。

板卡为领航者 V2，器件 xc7z020clg400-2。具体底板/核心板修订须核对实物，不得套用旧 AC7020 配置。配套 USB 接收器接收采集模块数据，另接板卡 USB_UART；两个串口均使用115200、8N1、无流控。先关闭占用端口的厂商软件、串口终端或备用客户端。模块供电、电极和电平按实际说明核对，本数字验证不能代替人体连接安全验收。

## 网页启动与采集

```powershell
python -m venv tmp/web_env
& ./tmp/web_env/Scripts/python.exe -m pip install -r src/web/requirements-lock.txt
./build/build_web.ps1
& ./tmp/web_env/Scripts/python.exe -B src/web/run.py
```

首次准备执行全部命令；日常只执行最后一行。打开终端显示的本机地址，注册本地账号（密码至少8位），登录后进入“实时与板卡”。端口占用时追加 --port 8001。前端更新后重新构建；已有依赖可用 ./build/build_web.ps1 -SkipInstall。依赖、网页dist、数据库和记录留 tmp/，由Git忽略。

默认网页分类为仓库HGB研究模型，固定v92/fold0，实际运算在电脑。网页Python与模型依赖不一致时，用ECG_HGB_PYTHON指定已通过完整自检的模型Python，详见[模型接入](model_integration.md)。旧src/web/.env若明确写none仍关闭分类，需改hgb后重启；不会自动覆盖已有设置。构建脚本使用UTF-8 BOM，兼容Windows PowerShell；已有依赖用SkipInstall时保留tmp中的依赖目录。

| 输入 | 选择方法 |
| --- | --- |
| 标准500Hz CSV→Zynq | 列为 index,sample,fs,scale，index从0连续，sample为int16，fs=500，scale=4096；不重复换算厂商码。 |
| 厂商CSV→Zynq | 原厂五列RawData文件，由客户端对CH2做标称换算和去直流。 |
| 蓝牙→Zynq | 选择配套接收器及独立Zynq串口，使用已确认的34字节帧。 |
| 只查看/日志回放 | 用于显示及排查；合成演示预设事件不是板端检测成绩。 |

先用5000点完成一轮（500Hz下约10秒），检查上传、确认、回显点数相等，无错误并收到 DONE。当前 latest 正常完成或“停止并保存”后无需复位，可以开始下一轮。停止后等待保存和串口释放；退出服务按 Ctrl+C。没有分类模型时 ?/-1 是正确的未知结果。

厂商来源默认在采集结束后自动提交完整记录到电脑HGB分析队列，按页面链接查看逐拍结果；浏览器离开不停止服务端提交。标准500Hz输入须先声明模型预处理状态。板端事件类别与电脑模型结果分别显示，不能把电脑分类写成板上模型推理。

### 使用板载ARM模型

需要装载双协议HGB固件；旧runtime500发布固件仍只有实时QRS，不会因为更新网页自动拥有模型。本机板卡已写入并通过QSPI掉电启动验证，新镜像构建ID为4a9c807c130595a9，latest仍保留旧匹配发布；重建步骤与证据见[报告](../report/report.md)。网页或后端已经打开时，保存会话后按原启动方法重启服务，以加载新代码及前端构建。

1. 在实时页选择“采集”或“文件”，处理方式选择板卡处理，刷新并选择Zynq USB_UART；采集时另选采集USB接收器，两个端口不能相同。
2. “Zynq ARM整段分类”默认勾选，切换到支持的板卡输入时也默认开启；只需原实时心率时手动取消。厂商输入直接使用完整原始CH2，内部按固定标称换算后送ARM；标准500Hz文件另声明hp05/raw，不能猜测或重复高通。
3. 每段最多30000点（60秒），建议先5000点验证；点击开始，等待收样、上传和整段分类完成。该模式结束后才返回模型结果，不是连续实时心率。需要原实时心率时取消勾选。
4. 页面必须标注“分类来源：Zynq ARM”和固定模型身份。下图是送板输入，标有“非板端波形回显”；类别为N/S/VF或未分类，VF为V/E/F合并，不表示心室颤动。下载result.json可取全部心拍与概率，tx.bin/rx.log用于追溯。
5. “电脑端模型分析”仍是独立报告功能；可取消自动分析来单独验证板载作用。启用两者时分别展示，不把电脑计算称为板载。

新双协议源码重建及打包：

```powershell
$env:ECG_HGB_WORKSPACE = '<仓库绝对路径>/tmp/hgb_dual_new'
$env:ECG_HGB_APP = 'batch'
$env:ECG_ARM_GCC = '<ARM工具链>/bin/arm-none-eabi-gcc.exe'
& '<Vitis>/bin/vitis.bat' -s board/build_hgb_test.py
python -B board/prepare_hgb_qspi.py --manifest tmp/hgb_dual_new/build_manifest.json --bootgen '<Vitis>/bin/bootgen.bat' --output tmp/hgb_qspi_new
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tmp/hgb_qspi_new/qspi/program_qspi.ps1 -CheckOnly
```

构建复用已验smoke硬件，不改PS/MIO；先用board/load_hgb.py临时下载、board/check_hgb_web.py核对实板（参数见--help），通过后在当前写Flash授权下使用生成目录中的program_qspi.ps1显式-Program。JTAG/QSPI拨码、全拔线掉电及校验步骤与下节相同；生成候选不等于写入或发布，不混用旧latest的BOOT.BIN。

## JTAG临时运行

使用 releases/latest/runtime500/ 匹配组合，不混用 smoke/bridge 的ELF或硬件。先检查：

```powershell
python -B sim/check_system_release.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -CheckOnly
```

已核对领航者启动表：JTAG为1=ON、2=ON，QSPI为1=ON、2=OFF，按实物编号复核。改拨码前断电，拔除所有可能供电的USB再上电。双击 releases/latest/runtime500/download.cmd，填写 xsdb.bat 路径及实际唯一JTAG序列号；或执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -Xsdb '<Vitis>/bin/xsdb.bat' -CableSerial '<唯一JTAG序列号>'
```

脚本校验文件和目标，初始化PS、加载匹配PL及应用。JTAG不写Flash，掉电失效。成功判据是收到 runtime500 就绪头并完成一轮回放，不能只看工具成功退出。不需要另建无关Vitis工程。

## QSPI掉电启动

已有本版镜像时按QSPI拨码上电即可。需要更换镜像时核对板卡型号/修订、供电和下载器，切JTAG并彻底掉电上电。第二条命令会覆盖偏移0的镜像区域，仅确需固化时执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/qspi/program_qspi.ps1 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/qspi/program_qspi.ps1 -Program -Xsdb '<Vitis>/bin/xsdb.bat' -ProgramFlash '<Vitis>/bin/program_flash.bat' -CableSerial '<唯一JTAG序列号>'
```

编程后切QSPI，拔除全部供电及USB再上电，连接串口完成回放。编程校验、PS复位启动与彻底断电启动分别验收。正常完成不擦写、不复位；错误后先保存日志，QSPI用PS系统复位恢复（不是PS_KEY1），JTAG重新下载应用。恢复前关闭当前连接，避免启动信息进入错误会话。

## 源码重建

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File board/rebuild_system.ps1 -Output tmp/rebuild_new -VivadoBin '<Vivado>/bin' -VitisBin '<Vitis>/bin' -Python '<Python环境>/python.exe' -Rate 500 -Trace 0
python -B board/prepare_qspi.py --release releases/latest --bootgen '<Vitis>/bin/bootgen.bat' --output tmp/boot_new
```

第一条生成新硬件和应用并核对PS/ECG参数；第二条从已发布组件重打包BOOT.BIN，不会采用第一条的新ELF。输出目录必须不存在。新构建不能自动替代已验latest，须另验匹配组合及实板行为。正式输入在 src/、build/、board/、vivado/，工具派生工程留 tmp/。

## 离线核对与排错

```powershell
python -B sim/check_repository.py
python -B sim/check_checkout.py
python -B sim/check_system_release.py
python -B -m unittest discover -s sim -p test_runtime_sessions.py
```

算法依赖见 data/requirements_qrs.txt，网页依赖见 src/web/requirements-lock.txt。失败先保存输出，再查文件哈希、输入fs/scale、串口是否选反或占用、是否使用旧固件。CRC、超时和硬件错误不能当正常结束，不自动重传数据包。启动杂字节、真实无线长时、拔插恢复和网页人工操作仍缺全面验收。[协议](protocols.md)定义实际字段，[当前实现与缺项](../report/report.md)说明验证边界。

## CH1呼吸波形显示

网页来源切换为“CH1 · 呼吸”时默认选择“呼吸显示滤波”；该选项只在记录确有处理字段时出现，旧记录缺字段会回退原码，可重新回放生成。PC采集后台以500Hz原码执行0.05Hz一阶高通和0.8Hz二阶Butterworth低通，跨普通传输块延续状态；每个新会话或样本索引断点重新初始化。滤波有相位延迟，前约10秒可能有启动过渡，建议点数上限设为30000（60秒）以上观察多个周期。它用于波形显示，不提供呼吸率、呼吸暂停判断或物理标定，也不表示FPGA执行了呼吸处理。

厂商v2.1.2程序的静态核查表明，CH1呼吸经过50Hz/Q=30陷波及0.1～0.5Hz带通，CH2为心电；本工程显示滤波参数与其不同，不能称逐值复现厂商波形。原码、厂商滤波列与本工程显示滤波分别保留。

原始CH1、厂商滤波列保留，新增samples.csv列resp_display_code和summary.json中的respiration_display参数。旧会话没有新增字段时不绘制软件滤波，须新建采集/CSV回放会话。滤波只能抑制噪声，不能修复电极接触、运动伪差或缺样。

## CH2心电三套数值

来源CH2保留本地默认“原始采集”，有标称电压时以mV显示。“信号”可切换原始采集、基线校正（0.5Hz一阶高通）、节律显示滤波（基线校正后40Hz二阶Butterworth低通＋50Hz Q=30陷波）；“单位”另选ADC码或标称mV，缺失字段不补算。滤波均为500Hz因果PC处理，状态跨块保持，新会话/索引断点重置，前约5秒为启动过渡。滤波可能改变幅值和相位，不用于ST段或诊断幅度判定。各档ADC码与mV使用同一固定换算，沿用当前工程2^23−1分母；与2^23口径相差约0.000012%，不影响直流偏置问题。

samples.csv新增ecg_baseline_code、ecg_baseline_mv（基线校正后的信号，非基线估计值）、ecg_display_code、ecg_display_mv；原始ADC和nominal.csv原始mV仍保留，summary.json记录ecg_display参数。典型生理幅值仅用于观察，不决定增益、裁剪阈值或归一化，不强行将峰值调成1mV。该显示链不替换模型输入或板端检测。旧会话无字段时不绘制，重新回放原始厂商CSV或新建采集即可生成。

## 网页纵轴和分类置信度

波形默认开启“归一化显示（仅绘图）”：当前可见窗口按极值居中缩放至[-1,1]，恒定信号画在0，叠加曲线共用尺度。纵轴无量纲，不是mV，也不适合跨窗口比较绝对幅度；取消勾选可恢复标题所示原单位。原始保存值、导出数据、模型输入和板端送样不变，事件时间和缺口不变。

HGB逐拍分类的结果卡显示“有效心拍平均置信度”，为有效心拍各自最大类别概率的平均值，并给出拍数和范围；逐拍概率仍在下方明细。无有效概率时明确显示未提供，不补零或正常类别。这是未校准模型概率的描述统计，不是整段诊断可靠性或检测准确率。
