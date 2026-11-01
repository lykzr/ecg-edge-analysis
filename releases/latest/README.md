# ECG系统JTAG与QSPI交付

本版为20261101-runtime500-session-reuse-v1，构建ID为36e807fd28c440f5。runtime500运行500Hz ARM端QRS检测、切拍及RR计算，支持正常完成或停止保存后重新等待下一轮握手。每轮重新初始化样本、心拍和RR状态；正常结束无需复位。协议错误、输入超时或硬件串口错误仍停止，保留现场后按对应启动方式恢复。

| 目录 | 用途 | 输入 |
| --- | --- | --- |
| runtime500/ | ARM检测、切拍与双向收发 | 500Hz、4096单位/mV，REPLAY/SYNTH/ADC |
| qspi/ | 匹配的掉电启动镜像与编程入口 | FSBL→bit→应用 |
| smoke/ | 独立基础自检 | 板端合成样本 |
| bridge/ | 旧PL检测器回归 | 仅显式legacy500，scale=-1 |

各组件只使用自己的匹配硬件、ELF和脚本。类别未知表示尚无最终分类模型，不是正常N；本应用不包含最终CNN、INT8或FPGA整网推理。

## 下载与运行

Windows双击runtime500/download.cmd，填写已有Vitis/bin/xsdb.bat路径和实际唯一JTAG序列号；或在工程根执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/runtime500/run_runtime500.ps1 -Xsdb '<Vitis>/bin/xsdb.bat' -CableSerial '<唯一JTAG序列号>'
```

CheckOnly只校验文件。下载入口核对字节数/SHA256和目标身份，再初始化PS、配置匹配PL并下载应用，不写Flash。临时JTAG程序掉电后失效；正常结束后可直接新建会话，错误停止后按下载流程恢复。无需管理员权限，ExecutionPolicy仅对当前进程生效。

默认按[网页教程](../../docs/download_guide.md)启动客户端，进入“实时与板卡”选择中转模式及实际USB_UART；Tk只作备用诊断。标准CSV须index,sample,fs,scale，fs=500、scale=4096。厂商五列RawData和34字节蓝牙输入走厂商入口，CH2去直流、标称mV换算及int16量化由客户端完成；不是电脑端QRS或CNN。参考电压/增益尚未实测标定，采集与Zynq使用两个独立串口，避免同时被其他软件占用。

## QSPI掉电运行

qspi/BOOT.BIN、fsbl.elf、boot.bif与runtime500中的bit/ELF匹配。已固化本版的板卡可从Flash直接上电运行，正常完成或停止保存后直接开始下一轮。异常停止时先保存错误，再用PS复位恢复；不是PS_KEY1。

为另一块匹配的领航者V2编程前，核对具体修订、供电、唯一下载器与启动表；按[下载教程](../../docs/download_guide.md)切JTAG并彻底掉电上电。默认只检查，显式-Program才覆盖偏移0的镜像区域，不整片擦除：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/qspi/program_qspi.ps1 -CheckOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File releases/latest/qspi/program_qspi.ps1 -Program -Xsdb '<Vitis>/bin/xsdb.bat' -ProgramFlash '<Vitis>/bin/program_flash.bat' -CableSerial '<唯一JTAG序列号>'
```

匹配领航者启动表为JTAG：1=ON、2=ON；QSPI：1=ON、2=OFF，仍须按实物编号核实。编程后切QSPI，拔除全部供电和USB再上电；串口115200/8N1/无流控。写入校验、系统复位和彻底断电启动分别验收，不能互相替代。

## 重建与证据

正式源码和构建入口在仓库src/、board/、build/；本包下载不依赖作者tmp。无需历史工作区的镜像重建：

```powershell
python -B board/prepare_qspi.py --release releases/latest --bootgen '<Vitis>/bin/bootgen.bat' --output tmp/boot_new
python -B sim/check_system_release.py
```

输出目录必须不存在。匹配文件、源码哈希、来源和分阶段证据见manifest.json、artifacts.json及[复用验收记录](../../report/report.md)。旧版原字节在作者本地保留，不作为本包运行依赖。有限数字回放不代表真实无线长时、拔插恢复、启动杂字节兼容、界面人工验收或分类准确率通过。

自有许可见LICENSE，第三方声明见third_party.md和仓库[许可入口](../../docs/licenses.md)；原应用/FSBL组成参考仍作为历史材料保留，本次实际ELF、FSBL、bit身份以artifacts.json和收据为准。供应商工具链补丁/IP分发边界及最终模型另行核对。本地交付不代表Git提交、推送或远端上传。
