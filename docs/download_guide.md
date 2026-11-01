# 使用、下载与重建

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

网页来源切换为“CH1 · 呼吸”，再在“信号”选择“呼吸显示滤波”；该选项只在记录确有处理字段时出现。PC采集后台以500Hz原码执行0.05Hz一阶高通和0.8Hz二阶Butterworth低通，跨普通传输块延续状态；每个新会话或样本索引断点重新初始化。滤波有相位延迟，前约10秒可能有启动过渡，建议点数上限设为30000（60秒）以上观察多个周期。它用于波形显示，不提供呼吸率、呼吸暂停判断或物理标定，也不表示FPGA执行了呼吸处理。

原始CH1、厂商滤波列保留，新增samples.csv列resp_display_code和summary.json中的respiration_display参数。旧会话没有新增字段时不绘制软件滤波，须新建采集/CSV回放会话。滤波只能抑制噪声，不能修复电极接触、运动伪差或缺样。

## CH2心电三套数值

来源CH2保留本地默认“原始采集”，有标称电压时以mV显示。“信号”可切换原始采集、基线校正（0.5Hz一阶高通）、节律显示滤波（基线校正后40Hz二阶Butterworth低通＋50Hz Q=30陷波）；“单位”另选ADC码或标称mV，缺失字段不补算。滤波均为500Hz因果PC处理，状态跨块保持，新会话/索引断点重置，前约5秒为启动过渡。滤波可能改变幅值和相位，不用于ST段或诊断幅度判定。各档ADC码与mV使用同一固定换算，沿用当前工程2^23−1分母；与2^23口径相差约0.000012%，不影响直流偏置问题。

samples.csv新增ecg_baseline_code、ecg_baseline_mv（基线校正后的信号，非基线估计值）、ecg_display_code、ecg_display_mv；原始ADC和nominal.csv原始mV仍保留，summary.json记录ecg_display参数。典型生理幅值仅用于观察，不决定增益、裁剪阈值或归一化，不强行将峰值调成1mV。该显示链不替换模型输入或板端检测。旧会话无字段时不绘制，重新回放原始厂商CSV或新建采集即可生成。
