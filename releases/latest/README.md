# ECG系统JTAG与QSPI交付

runtime500为当前500Hz ARM QRS/切拍程序，支持标准CSV及客户端内部处理后的厂商CSV/蓝牙采集输入。厂商CH2去直流/标称单位换算在仓库客户端内部完成，不是PC端QRS或CNN推理。

| 目录 | 用途 | 输入 |
| --- | --- | --- |
| runtime500/ | 当前ARM检测/切拍与双向收发 | 500Hz、4096单位/mV、REPLAY/SYNTH/ADC；无最终模型时类别未知 |
| smoke/ | 独立基础回归自检 | 板端合成样本 |
| bridge/ | 旧PL检测器回归 | 旧500Hz、scale=-1，仅显式legacy500 |

各组件使用自己的hardware、prebuilt和启动脚本，不交叉替换。正常运行关闭完整窗口跟踪。

## 下载与运行

Windows双击runtime500/download.cmd，按提示填写已安装的Vitis/bin/xsdb.bat路径及已核实的唯一JTAG序列号；也可在PowerShell指定参数：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -Xsdb '<Vitis>/bin/xsdb.bat' -CableSerial '<JTAG序列号>'
```

仅验证本地文件、不操作板卡：给同一入口加-CheckOnly。入口核对包内所有字节/SHA256，随后Tcl再次核对唯一Zynq-7020、复位、配置匹配PL/PS并下载应用。不写Flash，掉电或会话结束后重新下载；不需要管理员权限。ExecutionPolicy参数只作用于这次进程，不修改系统策略。

从仓库运行python -B src/ui/main.py，主窗口串口保持未连接，在送样/双向中转子窗口选择板卡USB_UART。厂商CSV用五列RawData按钮；蓝牙选择另外一个采集USB接收器端口。CH2自动去直流并按2.42V/PGA6标称换算，无需手动右移；参考/增益未实测标定。标准CSV须index,sample,fs,scale、fs=500、scale=4096，不再二次换算。

## 重建、许可与范围

正式源码/依赖和重建入口在仓库，见[下载教程](../../docs/download_guide.md)、[厂商输入](../../docs/vendor_input.md)和[构建说明](../../docs/system_checks.md)。本目录可单独用于JTAG，但客户端、许可原文、完整证据应随仓库查阅；没有作者tmp也能运行包内下载入口。

本地数字验收与来源见artifacts.json。真实无线/实际ADC节拍与标定、物理拔插/长时运行、新厂商界面人工检查和最终CNN/INT8/FPGA推理仍单独验收。QRS105噪声风险保留，不把有限数字回放当独立准确率或整机通过。

自有内容与第三方范围分别见LICENSE和third_party.md，原声明在仓库docs/licenses/，当前应用/配套FSBL实际组成见data/results/runtime500_components_20261025.json（FSBL未随JTAG包分发）。最终供应商工具链补丁/IP分发边界仍待核；本地更新不代表远端发布，QSPI固化及独立证据见下节。


## QSPI掉电保存

qspi/包含匹配BOOT.BIN、FSBL、BIF和编程/复位脚本；与runtime500共享同版bit/ELF，不重复复制硬件。镜像顺序为FSBL→bit→应用。

本版镜像已在本机板卡完成写入校验、用户彻底断电后QSPI启动及数字CSV回放；不代表接手者的板卡已写入。已经写好本版Flash的板卡，将BOOT_CFG设为1=ON、2=OFF后彻底断电上电即可运行。每轮结束后按PS复位键建立新会话，无需反复写Flash或JTAG下载。

给另一块匹配领航者板卡编程前，先核对具体硬件和唯一下载器，切为JTAG启动并彻底掉电上电；用qspi/program_qspi.ps1显式指定-Program、-Xsdb、-ProgramFlash和-CableSerial才写入。默认或-CheckOnly只验证本地文件，不连接板卡。该操作覆盖偏移0的旧启动镜像，只擦除镜像区域，不整片擦除。

无原构建工作区也能用board/prepare_qspi.py --release releases/latest --bootgen <Bootgen路径> --output tmp/boot_new重新打包；详见docs/download_guide.md和report/交接.md。QSPI编程、校验、系统复位和冷启动是分别验证的阶段，证据见artifacts.json，不继承为真实无线或CNN通过。
