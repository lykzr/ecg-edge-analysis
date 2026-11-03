# 使用、下载与重建

## 队友只拿Git时，从这里开始

先读[交接任务](../report/handoff.md)。正式源码、三份HGB权重、192特征代码、常量、合成输入/黄金结果、ARM实现、PL现有源码、构建脚本、许可和精选实板证据都随Git。必要入口列在[接手依赖表](../model/handoff_requirements.json)，不是让队友另外索取作者的tmp。**当前CNN/INT8/HGB PL推理交付见三核教程；原HGB训练来源仍未完整交付，不能称原训练复现已经完成。**

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

## HGB分类器的PL临时演示

这条路径把固定v92/fold0的192棵树放入PL，三类并行遍历。ARM仍负责特征生成及softmax；独立自检直接输入包内160组特征，当前不接网页采集协议。它不需要INT8、不训练，不提高模型既有质量指标。2026-11-01实板证据见[summary.json](evidence/hgb_pl_20261101/summary.json)与[串口原文](evidence/hgb_pl_20261101/serial.log)。不能把此证据写成整条采集链路或神经网络的加速。

数值约定：特征为float32，原double阈值转换为不大于它的最大float32并比较有序IEEE754位编码，正负零统一。叶值和基线按最邻近偶数舍入到有符号64位、40位小数，累加不溢出。单类理论分数量化误差上界约2.96e-11；492组软件核对的最大概率误差约1.67e-12、类别变化0，这不保证所有可能输入的类别都不变化。PL输出分类分数；概率的softmax仍在ARM完成。

首次生成及构建（PowerShell，位于仓库根目录；每次使用新输出目录）：

```powershell
$vivado = '<Vivado>/bin'
$vitis = '<Vitis>/bin'
$python = '<已安装numpy的Python>'
& $python build/export_hgb_pl.py --output tmp/hgb_pl_parameters_new
& "$vivado/vivado.bat" -mode batch -log tmp/hgb_pl_new.log -journal tmp/hgb_pl_new.jou -source build/build_hgb_pl.tcl -tclargs tmp/hgb_pl_hardware_new tmp/hgb_pl_parameters_new
$env:ECG_HGB_PL_WORKSPACE = "$PWD/tmp/hgb_pl_app_new"
$env:ECG_HGB_PL_HARDWARE = "$PWD/tmp/hgb_pl_hardware_new"
$env:ECG_HGB_PL_ROM = "$PWD/tmp/hgb_pl_parameters_new"
& "$vitis/vitis.bat" -s board/build_hgb_pl_test.py
```

独立仿真可执行 `sim/run_hgb_pl.ps1 -VivadoBin '<Vivado>/bin' -Python '<Python>' -Output tmp/hgb_pl_sim_new`，包括492组核心分数核对及AXI分离地址/数据、读写响应等待、错误输入检查。候选硬件复用正式领航者生成器，DDR/UART/MIO不改，保留QRS外设，额外增加HGB地址0x43C10000。与厂家6_axi_gpio_fsbl核对：器件、33.333333MHz晶振、DDR型号/频率及UART0 MIO14/15相同；厂家例程FCLK0为50MHz，本工程沿用既有100MHz并检查实现时序。

本机已生成的匹配组合：`tmp/hgb_pl_build_02/hgb_pl.bit`、同目录`hgb_pl.xsa`，`tmp/hgb_pl_vitis_01/hgb_pl_test/build/hgb_pl_test.elf`，`tmp/hgb_pl_vitis_01/hgb_pl_platform/hw/sdt/ps7_init.tcl`。文件哈希保存在上述summary.json；它们是本机候选，不是latest发布。

演示重放步骤：

1. 保持板卡供电、JTAG和USB_UART连接、原JTAG启动设置；结束网页采集。Vitis Serial Monitor选板端COM口、115200、8N1，可提前打开以接收日志。
2. 调试服务器运行时执行下列本机命令，仅对已经核实的唯一电缆有效：

```powershell
& '<Vitis>/bin/xsdb.bat' board/hgb_handoff/load.tcl 210512180081 tmp/hgb_pl_build_02/hgb_pl.bit tmp/hgb_pl_vitis_01/hgb_pl_platform/hw/sdt/ps7_init.tcl tmp/hgb_pl_vitis_01/hgb_pl_test/build/hgb_pl_test.elf
```

3. 应看到BEGIN、160行BEAT及`PASS HGB_PL vectors=160`。程序自动运行两轮核对，第一轮预热，第二轮计时；每组都核对ARM、PL及预期分数。结束后停在演示空循环，不会继续输出旧采集协议。脚本沿用加载器，所以`PASS HGB_BATCH_JTAG_STARTED`只代表下载启动，必须以串口`PASS HGB_PL`判断本自检成功。
4. 单行ARM_ticks和PL_call_ticks分别除以最终timer_hz得到秒；PL_cycles除以100000000得到纯核秒数。本次实测平均80.39µs、49.07µs及7.29µs；包含传输的调用加速约1.64倍，纯核约11.03倍。范围仅为树分数计算，不含检测、特征提取、softmax及串口。
5. 临时JTAG运行不会改变Flash。若要继续原网页采集，先关闭串口监视器，再按下面正式JTAG节加载原runtime500匹配组合；不要拿这个演示ELF配旧bit，也不要直接将候选写Flash。

HGB寄存器（相对0x43C10000）：

| 偏移 | 访问 | 含义 |
| --- | --- | --- |
| 0x00 | 读 | 标识0x48474231 |
| 0x04 | 写/读 | 写1启动；读bit0忙、bit1完成、bit2输入错误 |
| 0x08 | 读 | 本次纯核周期，包含启动/完成识别 |
| 0x0C | 读 | 时钟100000000Hz |
| 0x10/14、18/1C、20/24 | 读 | N/S/VF的64位Q40分数，先低32位后高32位 |
| 0x28 | 读 | 小数位40 |
| 0x100至0x3FC | 写 | 192项float32原始位，每项整32位写 |

复位后必须写齐特征；非有限值使对应项无效，启动返回错误。忙时写入、部分字节写或非法地址返回AXI SLVERR。运行期间分数未定，完成后再读取。连续分类必须在启动前更新全部192项；接口不会代替软件识别漏写的旧特征。

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


## 网页实测输入的PL分类

2026-11-01已使用用户ADS1292R原始文件通过网页HTTP接口、真实COM4及PL候选完整回放5148点。13个检测事件、12个有效分类、首拍未分类、裁剪0，ARM/PL分数不一致0。本次是离线实测文件回放，不是新的人体实时采集或专家分类评分。ECGHeatData为厂商心率摘要，不是模型输入。输入文件保留本地，不随Git发布。

当前匹配PL硬件仍为tmp/hgb_pl_build_02；整段固件为tmp/hgb_pl_batch_01/ecg_hgb_test/build/ecg_hgb_test.elf，初始化为tmp/hgb_pl_batch_01/ecg_platform/hw/sdt/ps7_init.tcl。重新构建设置ECG_HGB_WORKSPACE为新tmp目录、ECG_HGB_APP=batch、ECG_HGB_PL_HARDWARE和ECG_HGB_PL_ROM为已验硬件与参数目录、ECG_ARM_GCC为裸机工具链，执行Vitis `-s board/build_hgb_pl_batch.py`。入口pl_main.c与正式ARM main.c分开，正式latest不变。

网页操作：进入实时采集，选择“文件回放→厂商CSV经板卡处理（500Hz）”，上传ECGRawData文件，选择Zynq COM4；勾选“Zynq板端整段分类”。如只看板端结果，可取消电脑端自动分析。开始后等待完整送样；波形与事件区域将显示“Zynq FPGA PL · HGB Q40”及本次ARM/FPGA对比。串口监视器须关闭，避免占用COM4。每次计时随缓存与运行状态波动，展示本次原始计数，不使用固定演示值。事件表前的FPGA性能区域给出纯核、含传输及不一致拍数。导出result.json保留逐拍概率、位置及性能。

当前支持整段最多30000点，收齐后分析；实时蓝牙来源也先收整段，不能称逐拍实时PL调度。后续连续调度与Flash部署另行验收。


### 组员修改与重新下载

PL电路由仓库的src/rtl/ecg_hgb_core.sv、ecg_hgb_axi_lite.sv描述；ARM及PL访问代码在src/ps/ecg_hgb/pl_main.c、pl_tree.c。修改RTL需要重新运行Vivado综合/实现、生成bit和XSA；仅修改网页不需要重新生成PL。当前通过JTAG加载到易失配置存储器，断电不保留；烧入QSPI需要另外制作匹配启动镜像并验收，不能只把某个源码文件“写进板子”。

从main克隆后，不要求存在开发者的tmp目录。完成上面的参数导出和候选硬件构建，再按以下命令生成整段网页分类固件（使用刚生成的路径）：

```powershell
$env:ECG_HGB_WORKSPACE = "$PWD/tmp/hgb_pl_batch_new"
$env:ECG_HGB_APP = 'batch'
$env:ECG_HGB_PL_HARDWARE = "$PWD/tmp/hgb_pl_hardware_new"
$env:ECG_HGB_PL_ROM = "$PWD/tmp/hgb_pl_parameters_new"
$env:ECG_ARM_GCC = '<Vitis>/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe'
& '<Vitis>/bin/vitis.bat' -s board/build_hgb_pl_batch.py
& '<Vitis>/bin/xsdb.bat' board/hgb_handoff/load.tcl <实物电缆序列号> tmp/hgb_pl_hardware_new/hgb_pl.bit tmp/hgb_pl_batch_new/ecg_platform/hw/sdt/ps7_init.tcl tmp/hgb_pl_batch_new/ecg_hgb_test/build/ecg_hgb_test.elf
```

运行前确认目标板、JTAG启动设置、电缆唯一及COM口释放，并启动hw_server。这里的尖括号为需要替换的参数，不能原样执行。加载器仅操作唯一匹配Zynq-7020；日志中的STARTED不能代替实际分类验收。构建产物留tmp，不随源码提交；最新正式QSPI镜像仍在releases/latest，未被候选替换。

## 四分类CNN训练交接分支

另一位队员接续训练使用 `training/cnn-fourclass-h27`，按[完整训练接手说明](cnn_training_handoff.md)克隆、核验权重、重建允许数据并先做0拟合预检。`model/cnn_fourclass/train.py`默认不训练，只有显式 `--train` 才进行有限续训；本次交接没有执行续训。三个fold分别对应固定留出患者，不能按各折成绩挑一个冒充正式部署模型。ARM独立运行见下节；CNN/HGB双模型PL与网页操作见本页末节。INT8仍未完成。

## H27 CNN在Zynq ARM临时运行

H27不要求先量化：使用fold0、FP32，C实现包含卷积/残差/池化/全连接、122项因果形态特征和RR历史；板上不需要Python/PyTorch。fold0仅作固定联调选择，不是正式合格模型。本节保留独立ARM候选教程；新版PL的独立实测见下节，既有HGB PL成绩不能沿用到CNN。

在仓库根目录执行以下命令。尖括号均需替换；新输出目录必须尚不存在。主机Python需NumPy、SciPy、PyTorch；本机Python3.13使用独立tmp/cnn_env（torch2.15.0+cpu）已通过原包36个黄金样例，不改原训练依赖、不训练。HOST_GCC为已有Windows GCC，VITIS为安装根下Vitis目录。

```powershell
$py = '.\tmp\cnn_env\Scripts\python.exe'
$vitis = '<Vitis绝对路径>'
$hostcc = '<已有主机gcc.exe绝对路径>'
& $py model/cnn_fourclass/check.py
& $py sim/check_cnn_arm.py --cc $hostcc --output tmp/cnn_arm_verify_new
& $py build/export_cnn_arm.py --output tmp/cnn_parameters_new
$env:ECG_CNN_PARAMETERS = "$PWD/tmp/cnn_parameters_new"
$env:ECG_CNN_HARDWARE = "$PWD/tmp/hgb_pl_build_02"
$env:ECG_CNN_WORKSPACE = "$PWD/tmp/cnn_arm_new"
$env:ECG_ARM_GCC = "$vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe"
& "$vitis/bin/vitis.bat" -s board/build_cnn_arm.py
```

ECG_CNN_HARDWARE必须包含匹配领航者V2配置的hgb_pl.bit/xsa。本机复用已验tmp/hgb_pl_build_02；新克隆先按上文HGB PL硬件重建命令生成，再把该变量改为实际目录。这里PL仍装载既有HGB硬件，但CNN程序完全在ARM执行，不调用HGB PL。

板卡供电、JTAG与USB_UART接好，按上文核实JTAG启动，关闭所有串口监视器/网页采集。先启动匹配工具的hw_server（3121），枚举USB身份，再临时下载。Vitis2026.1使用xsdb.bat，xsct已禁用。

```powershell
& $py -c "import sys,json;sys.path.insert(0,'src/pc');from ecg_ports import enumerate_ports;print(json.dumps(enumerate_ports()))"
& $py board/load_cnn.py --manifest tmp/cnn_arm_new/build_manifest.json --xsdb "$vitis/bin/xsdb.bat" --cable '<实物JTAG序列号>' --port '<实际COM口>' --device-id '<枚举的device_id>' --output tmp/cnn_load_new
& $py src/pc/ecg_cnn.py --input-mv tmp/cnn_arm_verify_new/synthetic500_mv.csv --port '<实际COM口>' --device-id '<枚举的device_id>' --preprocess hp05 --output tmp/cnn_run_new
& $py sim/check_cnn_board.py --directory tmp/cnn_run_new --input-mv tmp/cnn_arm_verify_new/synthetic500_mv.csv
```

真实ADS CSV先对ecg_raw按 `(ecg_raw-8388608)*2420/(6*8388608)` 生成无表头单列mV文件；已是mV的文件不重复换算，不用ecg_filtered。也可给check_cnn_arm.py追加 `--real-csv '<厂商原始CSV>'`，该脚本在本地输出ads1292r_mv.csv及对照数据。健康原始数据和完整串口原文留tmp，不上传。

当前本机最终候选为tmp/cnn_arm_build_02，ELF在ecg_cnn_arm/build/ecg_cnn_arm.elf。每条完整记录最多30000点/60秒，记录间重建状态；输入传完才开始检测与分类，不能称连续实时逐拍。结果N/S/V/F的F为融合拍；首RR未知或窗口不足保留未分类。rx.log/tx.bin/result.json/comparison.json为运行及对照证据；classify耗时包含背景/形态特征与CNN，不含串口，不是纯卷积耗时。此处独立ARM候选使用上述命令；新版双模型PL网页入口见下一节。恢复网页HGB须重新临时加载匹配HGB ELF，或按原有QSPI流程断电启动。未写Flash、未替换latest。


## CNN与HGB在同一PL镜像中演示

2026-11-02候选同时保留H27 fold0 FP32全网络和HGB v92 fold0 Q40分类树，由网页分别选择，不是模型投票。当前本机匹配组合为tmp/cnn_pl_build_01/cnn_pl.bit/xsa、tmp/cnn_dual_vitis_01/ecg_cnn_arm/build/ecg_cnn_arm.elf和该Vitis目录的ecg_platform/hw/sdt/ps7_init.tcl。完整哈希与实测范围见[候选证据](evidence/cnn_pl_20261102/summary.json)。JTAG临时运行断电丢失，未替换latest或写Flash。

板卡已加载此候选时不用再次烧录。在仓库根运行 `& build/build_web.ps1 -SkipInstall`，再运行 `& tmp/web_env/Scripts/python.exe src/web/run.py --port 8000`。浏览器打开http://127.0.0.1:8000，登录原本地账号，进入“检测与加速”，选择“文件回放→厂商CSV · 板卡处理（500Hz）”，上传ECGRawData原始CSV，选择实际Zynq USB_UART（本机COM4），保留“板端心拍分类”，先选CNN。关闭其他串口终端。

点击“开始并记录”，收齐后显示N/S/V/F数量、R峰、心率、逐拍概率及本次ARM/FPGA对比。同一文件再选HGB可查看N/S/VF，轮间不需要复位。取消“按采样节拍回放”可更快传完文件，不改变采样率或时间轴。实时采集也按指定点数收齐后分类，每段最多60秒，不是无限连续逐拍推理。高级区保留电脑HGB分析，来源独立。

3分钟演示可依次展示板卡和连接、真实采集文件回放、CNN分类与本次同板ARM/FPGA含传输对比，最后切HGB证明两模型均保留。受控合成数据可展示S/V事件，但须明确标记为合成。模型概率未校准，不是诊断可靠性。真实HTTP和串口已验，浏览器视觉效果仍需人工确认。

### 从源码重建双模型候选

先按前文导出HGB PL参数，含mem与hgb_pl_fixture.c/h。Python环境需NumPy、SciPy、PyTorch，工具使用本轮已验2026.1。new输出必须不存在，尖括号须替换实际路径。HLS使用现代配置入口，避免2026.1旧Tcl的add_files布尔参数识别问题。

```powershell
$py = '.\tmp\cnn_env\Scripts\python.exe'
$vitis = '<Vitis绝对路径>'
$vivado = '<Vivado绝对路径>'
& build/run_cnn_hls.ps1 -VitisBin "$vitis/bin" -Python $py -Parameters tmp/cnn_hls_params_new -Output tmp/cnn_hls_new -Cosim
& "$vivado/bin/vivado.bat" -mode batch -source build/build_cnn_pl.tcl -tclargs tmp/cnn_pl_new tmp/hgb_pl_parameters_new tmp/cnn_hls_new/hls/impl/ip
$env:ECG_CNN_PL = '1'
$env:ECG_CNN_PARAMETERS = "$PWD/tmp/cnn_hls_params_new/arm"
$env:ECG_CNN_HARDWARE = "$PWD/tmp/cnn_pl_new"
$env:ECG_CNN_WORKSPACE = "$PWD/tmp/cnn_dual_new"
$env:ECG_HGB_PL_ROM = "$PWD/tmp/hgb_pl_parameters_new"
$env:ECG_ARM_GCC = "$vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe"
& "$vitis/bin/vitis.bat" -s board/build_cnn_arm.py
```

检查12组HLS黄金样例、RTL cosim与实现时序通过，再核实实物、电缆唯一、USB身份及临时运行授权；按前节启动hw_server：

```powershell
& $py board/load_cnn.py --manifest tmp/cnn_dual_new/build_manifest.json --xsdb "$vitis/bin/xsdb.bat" --cable '<实物JTAG序列号>' --port '<实际COM口>' --device-id '<实际device_id>' --output tmp/cnn_dual_load_new
& tmp/web_env/Scripts/python.exe board/check_cnn_web.py --port '<实际COM口>' --device-id '<实际device_id>' --source '<厂商原始CSV>' --output tmp/cnn_web_check_new
```

第二条用隔离本地账号/数据库执行CNN→HGB→CNN真实HTTP与串口检查，完整快照只留tmp，不修改现有账号或上传数据。也可沿用前节CLI送样及check_cnn_board.py复算。改HLS或权重需重生成IP/bit/XSA/ELF；仅改网页重构网页；改ARM重建匹配ELF。当前实际HLS工程为tmp/cnn_hls_07，参数tmp/cnn_hls_parameters_01，HGB参数tmp/hgb_pl_sim_02。

CNN四路输出通道并行、空间交错累加，保持FP32点积次序。100MHz、CNN AXI 0x43C20000，原HGB/QRS地址与PS7/DDR/MIO配置保留。ARM负责高通、QRS/切拍、形态及历史特征、softmax；PL负责整个CNN网络或HGB分类树。CNN“计算等待”包含ARM轮询误差；“含传输”包含寄存器读写，两者不含检测/特征/UART/网页。调试固件每拍先ARM后PL核对，因此整段等待时间不能称部署后的最短延迟。INT8、持续调度、模型融合与Flash冷启动仍待完成。


## 新增CNN实时模式，保留两种整段模式

本轮新增CNN流式功能，不替换原CNN/HGB整段功能。网页板端模型选择CNN后，“分析模式”可选“CNN整段分析 · 原功能”或“CNN实时分析 · 边采边测”；默认整段。HGB继续整段分析。不要把“按采样节拍回放”（控制文件送入速度）与“实时分析”（板卡是否逐拍输出）混为一项。

当前本机已临时加载流式ARM固件tmp/cnn_stream_vitis_01，沿用上一版tmp/cnn_pl_build_01的bit/XSA，无需重新综合PL。重新上电后需按前节load_cnn.py使用 `--manifest tmp/cnn_stream_vitis_01/build_manifest.json` 再临时加载。组员从源码重建仍用前节HLS/硬件及Vitis入口，ECG_CNN_WORKSPACE换新目录；构建器自动加入stream.c/h与stream_uart.h。没有Flash更新，也未替换latest。

1. 关闭Vitis串口终端，打开http://127.0.0.1:8000，在“检测与加速”选择Zynq实际串口（本机COM4）。
2. 用文件验证：选择“文件回放→厂商CSV · 板卡处理（500Hz）”，上传ECGRawData，模型选CNN、模式选实时；勾选按节拍回放可观察结果边传边出。不需要等待文件结束。
3. 用实际ADS采集：选择“实时采集→板卡处理”，分别选择Zynq USB_UART和采集USB接收器两个不同串口，填写点数上限，选择CNN实时。保持采集模块和接收器按原工程配置。本轮实测为已有ADS文件回放，真实无线同时采集需使用者在场验证。
4. 逐拍表显示ARM/FPGA各自类别、网络耗时、算法等待和PC收到结果的延迟。性能区持续更新平均值、累计总时间及倍数；点击停止后送完已采队列，保存已有分类，末窗不足保持未分类。
5. 选择CNN整段、或切HGB整段，仍可完成原分析；三种模式需不同会话，不能在同一会话中途换模型。

性能是同拍先ARM再FPGA，网络输入和FP32相同；无需两者同时执行才能比较。累计FPGA时间包含AXI寄存器传输，但不含PC到板UART。采集时长、算法等待、串口回传和浏览器刷新不计为网络加速。当前不显示电脑CPU对比，因为尚未接入同输入/同精度/统一计时的CPU基准；不拿PyTorch初始化或整段Python时间与纯PL混比。

已授权板测时可运行下列复核，尖括号需替换；新输出目录必须不存在：

```powershell
& tmp/cnn_env/Scripts/python.exe board/check_cnn_stream.py --source '<无表头单列500Hz原始mV.csv>' --port '<COM口>' --device-id '<USB身份>' --output tmp/cnn_stream_check_new --realtime
& tmp/web_env/Scripts/python.exe board/check_cnn_web.py --source '<厂商ECGRawData.csv>' --port '<COM口>' --device-id '<USB身份>' --output tmp/cnn_stream_web_new --streaming
```

第一条逐拍与冻结PyTorch对照，验证结束前有结果；第二条隔离账号做CNN实时→HGB整段→CNN实时HTTP实板切换。再追加 `--stop-after 2000` 验证第一轮主动停止及后续复用；不加--streaming则复测原CNN整段→HGB整段→CNN整段。原始健康数据及交互只留tmp。证据见[流式实测](evidence/cnn_stream_20261102.json)。真实无线、满1小时、物理断线恢复、INT8与双模型融合不在此次已验范围。

## INT8 独立候选与量化对比（2026-11-03 候选实测通过）

**组员从Git克隆后优先使用[三核交付教程](../board/cnn_triple_20261103/README.md)**：配套镜像、离线哈希检查、可移植JTAG加载、合成回放文件、Vivado原始布局布线DCP及统一源码重建入口均在仓库。下文tmp路径仅记录原本机验证来源，不能作为组员已有文件的前提。

原 CNN FP32 整段/实时及 HGB 整段保留，默认精度仍为 FP32。网页新增“计算精度 → INT8 · 量化 CNN 对比”，只接受 `ECG-TRIPLE-1` 候选固件，旧固件会在送样前拒绝。当前前后端、RTL联合仿真、布局布线时序、JTAG与网页CSV回放板测均已通过；没有修改 `releases/latest`。

量化采用动态 W8A8：每输出通道 INT8 权重、每层每拍动态 INT8 激活、INT32 累加；FP32 缩放/偏置/残差保留。不是全整数实现，不使用患者校准，不重训。并行度也与原 FP32 核不同，性能变化不能全部归因于位宽。

在仓库根使用已有 PyTorch 环境及本机工具，输出目录必须是全新 tmp 子目录：

```powershell
$py = '<含PyTorch及numpy的Python>'
$vitis = '<Vitis绝对路径>'
$vivado = '<Vivado绝对路径>'
& $py build/export_cnn_int8.py --output tmp/cnn_int8_params_new
& $py sim/check_cnn_int8.py --parameters tmp/cnn_int8_params_new --output tmp/cnn_int8_host_new --cc '<本机g++.exe>'
& build/run_cnn_int8_hls.ps1 -VitisBin "$vitis/bin" -Parameters tmp/cnn_int8_params_new -Output tmp/cnn_int8_hls_new -Cosim
& "$vivado/bin/vivado.bat" -mode batch -source build/build_cnn_int8_pl.tcl -tclargs tmp/cnn_int8_pl_new tmp/hgb_rom_new tmp/cnn_hls_new/hls/impl/ip tmp/cnn_int8_hls_new/hls/impl/ip
```

FP32 IP 与 HGB ROM 先按上一节生成。系统构建沿用原 PS7、DDR、MIO 与 100MHz AXI 时钟，仅新增 `0x43C30000` INT8 IP；需要 RTL 联合仿真和 routed 时序均通过后才使用镜像。受限内存主机的综合采用 jobs=1；主机失败保留日志，`build/resume_cnn_int8_pl.tcl` 仅用于恢复 tmp 候选。

生成 XSA 后按原双模型构建命令设置 `ECG_CNN_PL=1`、`ECG_CNN_HARDWARE`、`ECG_CNN_PARAMETERS`、`ECG_HGB_PL_ROM`、`ECG_CNN_WORKSPACE`、`ECG_ARM_GCC`，额外设置：

```powershell
$env:ECG_CNN_INT8 = '1'
$env:ECG_CNN_INT8_PARAMETERS = '<新INT8参数绝对目录>'
& "$vitis/bin/vitis.bat" -s board/build_cnn_arm.py
```

构建成功不等于板测通过。临时 JTAG 加载须确认实物、串口释放及本次下载授权，仍用 `board/load_cnn.py`，不写 Flash。网页构建用 `build/build_web.ps1 -SkipInstall`；不要在正式 src 下安装依赖或生成 dist。

INT8 对比模式同一拍依次执行 FP32 ARM→FP32 PL→INT8 ARM→INT8 PL，Q 报文记录四项网络累计时间。网页显示每拍均值及 FP32时间/INT8时间，小于1表示量化后更慢；这不是四路并行吞吐。原 P/T 性能字段在 INT8 模式代表同精度 INT8 ARM/PL，量化类别变化另计，不等于硬件错误。算法窗口等待、采集与串口不混入网络加速比。

资源 API `/live/accelerators` 使用固定证据 `docs/evidence/cnn_int8_20261103/resources.json`，无证据返回 pending。表中区分同一镜像内各 CNN 核与系统总量，BRAM36 为36Kb tile单位；不能把 HLS BRAM18K 与 routed BRAM36直接相比。FP32、INT8同时保留会增加系统总占用，不能要求总量比旧双核镜像更低。

本机已临时运行组合：tmp/cnn_int8_pl_build_01/cnn_pl.bit/xsa + tmp/cnn_int8_vitis_02/build_manifest.json，前后端地址 http://127.0.0.1:8000。保持板卡供电，在网页选择板卡COM9（以当前枚举为准）→CNN→计算精度INT8→整段或实时→选择CSV回放或ADS采集。CSV整段和节拍回放已板测，真实蓝牙并发尚未本轮验证。JTAG断电丢失，下次上电使用此manifest按前文load_cnn.py重载，未写Flash。

同拍72有效拍实测：FP32 ARM/PL 8.250/2.763ms，INT8 ARM/PL 7.694/1.368ms；PL均含板内寄存器传输，INT8较FP32约2.020倍，同精度INT8 ARM/PL约5.624倍。网页会依据本次累计tick更新。两核并行度不同，不把全部增益归因于位宽。真实CSV12有效拍类别无变化、合成72拍5拍变化，非准确率验收。资源与测试范围见[候选证据](evidence/cnn_int8_20261103/summary.json)。

## 带mV导联列的360Hz CSV转换

对于表头sample_index,time_s,MLII_mV,V1_mV且时间连续的数据，使用网页环境的NumPy/SciPy执行以下命令。源单位必须已是mV，不做ADS ADC换算。

```powershell
& tmp/web_env/Scripts/python.exe build/convert_ecg_mv_csv.py --input "<源CSV绝对路径>" --output tmp/patient_csv_new --lead MLII_mV --source-hz 360
```

输出必须是新目录；脚本校验序号/时间轴，正规重采样至500Hz，按4096单位/mV取整成int16，超范围拒绝，分成最多60秒的标准CSV。网页文件回放选择其中一份，CNN/HGB均使用500Hz；每份独立会话，不跨段计算RR。转换未加高通，源数据若确认未做额外数字滤波，选“未额外滤波→模型hp05”；来源处理未知时不能声称与模型预处理合同完全匹配，不要随意选raw。conversion.json保留来源哈希、分段位置和方法；未转换心拍标注，不可直接拿原标注索引计分。

## FP32全连接并行与工作灯候选

在原三核重建命令末尾增加 `-FastWorkLed`，并使用新的 `-Name`。默认不带此参数仍构建原三核设计。候选保留FP32/INT8 CNN整段和实时、HGB整段及原有计时协议，只将FP32全连接改为四输出并行，不重训、不改权重、各输出的累加次序不变。

```powershell
& build/rebuild_cnn_triple.ps1 -Python '<含PyTorch的python.exe>' -Vitis '<Vitis目录>' -Vivado '<Vivado目录>' -Name cnn_fast_led_new -FastWorkLed
```

该入口依次导出参数、HLS综合和RTL联合仿真、Vivado三核实现、Vitis裸机程序，不下载。独立核对新旧数值可执行 `sim/check_cnn_fast.py --parameters <候选fp32_params> --output tmp/cnn_fast_native_new --cxx <已有g++.exe>`；工作灯仿真入口为 `sim/run_activity_led.ps1 -VivadoBin <Vivado/bin> -Output tmp/activity_led_new`。只有时序通过和匹配manifest生成后，才按原 `board/load_cnn.py` 流程临时加载；旧 `board/cnn_triple_20261103` 和 `releases/latest` 保留。

工作灯采用领航者V2底板的 `PL_LED0`：H15、LVCMOS33、高有效，与资料盘官方 `1_led` 例程一致。核心板2V5原理图第3、7页确认BANK35及默认3.3V供电；J16是核心板另一颗PL灯，本候选不使用。AXI GPIO地址 `0x43C40000`，PL使用原100MHz时钟生成2Hz闪烁，PS在分析会话开始/退出时开关；空闲、取消、错误返回或复位熄灭。它表示板端会话运行，包括收样/等待，不是逐周期CNN运算忙信号。资料修订或BANK35供电被改动时须重新核对约束。

手动构建匹配Vitis程序时，除原三核环境变量外设置 `ECG_ACTIVITY_LED=1`；该开关只与含工作灯GPIO的XSA配套，禁止对旧镜像开启。候选在独立生成的main副本中包裹会话入口，原封印main、ARM网络和计时函数保持原字节。网页仍按本次P/T/Q报文计算加速比，不能由HLS周期直接宣称实板速度；资源须使用该候选的routed报告，不能沿用旧镜像数字。

本机已验匹配清单是 `tmp/cnn_fast_vitis_01/build_manifest.json`，硬件工程为 `tmp/cnn_fast_pl_02/cnn_pl.xpr`。断电后需重新临时加载，在核对本次目标与授权后用前文 `board/load_cnn.py --manifest tmp/cnn_fast_vitis_01/build_manifest.json`，其他参数仍填实际电缆号、端口、USB身份及全新output。板上含传输FP32实测约4.17倍，INT8约5.62倍；资源与限制见 `docs/evidence/cnn_fast_20261103/summary.json`。前端“硬件信息”改用该候选静态报告；如切回旧镜像，资源入口也须对应切回旧证据。不要同时运行板测脚本、串口监视器与网页采集，Windows错误码5通常表示端口被占用；先结束占用方后重试，不需要重复烧录。

## INT8并行候选的独立验证

**Git 克隆后的当前匹配镜像和 Vivado 实现快照入口：[优化版三核交付](../board/cnn_fast_20261103/README.md)。** 下文 tmp 路径是本机历史构建位置；组员直接加载应使用该目录的 `check.py` 和 `load.py`，不需要索取原作者 tmp。

进一步候选使用 `-FastWorkLed -Int8Fast -Conv16`。`-Int8Fast` 将INT8的269→64全连接层改为四输出并行，`-Conv16` 进一步将卷积输出通道从8路改为16路、权重ROM请求使用LUTRAM；不改变原量化规则、权重、INT32累加及FP32缩放/偏置。原FP32快核、HGB、工作灯和接口保留。省略这两个新参数仍走已存在流程。

```powershell
& build/rebuild_cnn_triple.ps1 -Python '<含PyTorch的python.exe>' -Vitis '<Vitis目录>' -Vivado '<Vivado目录>' -Name cnn_int8_fast_new -FastWorkLed -Int8Fast -Conv16
```

新构建在综合后检查全系统BRAM36等效总量不超过130.5块；超过即停止，不替换原镜像。HLS估算与布局布线资源分开，综合/仿真未通过的候选不可下载。软件逐位对照入口如下，覆盖原INT8、全连接四路和卷积16路三个核及独立Python整数参考：

```powershell
& '<含PyTorch的python.exe>' sim/check_cnn_int8_fast.py --parameters tmp/cnn_int8_fast_new/int8_params --output tmp/cnn_int8_fast_check_new --cxx '<已有g++.exe>'
```

单独生成Vitis匹配程序时，额外设置 `ECG_CNN_INT8_FAST=16`（仅全连接候选填4），使manifest封印实际候选源码和ROM；ARM仍使用原整数参考核。候选的离线数值一致性不代表消除了原INT8与FP32之间的量化偏差，也不能代替专家标注准确率或实板提速验证。

本机已通过候选的匹配清单为 `tmp/cnn_int8_fast_vitis_01/build_manifest.json`，硬件工程为 `tmp/cnn_int8_fast_pl_01/cnn_pl.xpr`；临时JTAG及60秒整段/流式板测通过，未写Flash。网页选择CNN、INT8与原有整段或边采边测即可，原FP32/HGB保留。60秒合成72有效拍INT8含寄存器传输约0.854ms、同精度ARM约7.695ms（约9.01倍）；相对FP32 PL约2.315倍。报告静态资源使用本镜像122.5/140块BRAM36，不再套用前一镜像的130.5块；切回旧镜像须同步切资源证据入口。该倍数不含采集、UART、滤波、特征及浏览器。新旧INT8的73条事件位置/状态/类别/概率完全一致，原量化相对FP32的5拍类别变化保留，不能称分类准确率提升。
