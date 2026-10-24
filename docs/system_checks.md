# 系统构建与检查

## 从正式源码完整重建

Windows原生PowerShell使用一个入口完成BD、综合、实现、bit/XSA/初始化、FSBL和ARM应用构建；不连接板卡。输出必须是项目tmp下不存在的英文短路径。工具和Python使用本机已有安装，不下载或安装依赖。

```powershell
& ./board/rebuild_system.ps1 -Output tmp/build_new `
  -VivadoBin '<Vivado安装目录>/bin' -VitisBin '<Vitis安装目录>/bin' `
  -Python '<已有Python解释器绝对路径>' -Rate 500 -Trace 0
```

`-Rate`只允许360或500，默认360；`-Trace`默认0。入口给子进程明确设置采样率与跟踪配置，最后检查实际构建清单，终端残留环境变量不会覆盖显式参数。源目录本身也须满足当前工具的路径限制，建议无空格英文短路径。PS7/MIO/DDR及旧PL配置沿用正式BD，500选择的是ARM处理分支，不修改这些硬件参数。

输出包括hardware_build/hardware内的bit、XSA、ps7_init、BD、时序/资源/DRC报告；sw/ws内的应用、独立FSBL、两份实际链接图及build_manifest.json；顶层summary.json只在软硬件全部成功后生成。失败目录和日志保留，不自动恢复/覆盖或发布。

Python入口`board/rebuild_system.py --rate 500 --trace 0 ...`也保留，主要供软件阶段与显式`--hardware-from`接续使用；Windows完整流程优先上述原生PowerShell入口。接续会在摘要中标明硬件来源，不能当成该次从零生成硬件。

## 数字验收与窗口跟踪

正常运行不发送128点窗口的十六进制调试跟踪，仍保留波形W、事件E、状态T和分类未交付说明。窗口跟踪只在`-Trace 1`或独立软件构建`ECG_RUNTIME_TRACE=1`时开启；它增加带宽与等待，不适合用作高负载持续运行配置。

360Hz逐窗口验收脚本要求清单声明跟踪开启，并从该清单提取唯一bit、XSA、初始化和ELF，逐项验证SHA，不再固定下载旧latest文件。该脚本明确拒绝500Hz清单；新500Hz实板验收仍待单独完成，不能拿旧脚本静默改变采样率。

T状态重复最近已知事件的心率/RR；尚无已知RR时仍为-1。它不是新的心拍事件，也不证明采集仍在继续，客户端仍依据合法波形接收间隔标记历史状态。输入结束后的残缺USB行必须报失败。

## 500Hz负载边界

```powershell
python -B sim/check_rate500_load.py --output tmp/load_new
```

实际C流程连接有界虚拟UART：两向115200/8N1分别最多11520字节/秒、板端TX FIFO64字节、固件发送队列8192字节、电脑输入队列默认4096点；PC读节拍、源集中到包、接收缓存与调试跟踪分别施压。用同一输入比较正常与受压事件位置/RR；队列满、接收溢出、发送停滞应明确终止，不自动丢样或重传。

该模型不模拟ARM计算周期、Windows驱动/USB调度或真实蓝牙，因此延迟是虚拟传输加因果检测/切拍等待，不是板端实测性能。任意慢接收都能保持500Hz没有保证：一包在途且每包最多32点，确认读取过慢会降低吞吐。默认记录还有64MiB总限额，达到限额应停止保存现场，不能把本测试解释为无限时长运行能力。

## 实际二进制许可证据

```powershell
python -B sim/check_binary_licenses.py --root '<对应源码根>' `
  --manifest '<软件工作区/build_manifest.json>' `
  --tool-bin '<Vitis>/gnu/aarch32/nt/gcc-arm-none-eabi/bin' `
  --output tmp/binary_licenses_new
```

要求应用和FSBL各自的ELF及链接图全部在清单内，核对库文件SHA、实际提取的archive成员、最终保留符号和编译器版本。`LOAD`只是链接输入，不证明整库进入ELF；被提取的成员也可能有section被gc丢弃。版权、上游版本声明和供应商二进制对应关系分别记录，不能把MIT自有源码许可覆盖到全部产物。

第三方许可入口为[裸机许可](licenses.md)。最终模型、供应商工具链补丁对应关系、适用IP条款和最终发布仍须单独核对；本入口不公开上传或替换latest。


## 当前开发与冻结发布分开检查

`sim/check_system_release.py`默认严格核对发布产物、证据和当前源码SHA；开发源码改变后应拒绝，不能改旧manifest冒充匹配。`--artifacts-only`只检查冻结产物/证据完整，并明确输出source_drift和current_rebuild_qualified=false；不会授予新发布资格。

开发中的干净回归可显式运行`python -B sim/check_system_offline.py --output tmp/offline_new --clean-copy --release-artifacts-only`。结果中current_release_rebuild_qualified必须如实保留；没有此参数时仍按严格发布源码门禁。新厂商500Hz固件的构建/使用见[厂商接入](vendor_input.md)，模型和真实无线边界不因此取消。
