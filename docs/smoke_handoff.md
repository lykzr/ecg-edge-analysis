# smoke自检与交接

smoke用于检查PS→AXI→原QRS检测器→事件FIFO基础链路。修改RTL、寄存器或PS接口后可作为回归自检；它使用合成输入，不测试真实AFE/ADC、新候选峰算法或CNN。JTAG临时运行不写Flash，掉电需重新下载。

## 使用哪个工程

优先使用[当前smoke交付](../releases/latest/README.md)中的匹配bit/XSA/初始化文件与ELF，按该入口运行；不要混入旧Hello World镜像。已有本机Vitis工作区、完整预期输出、复位/拨码和串口步骤统一见[下载教程第20节](download_guide.md#20-ps-读取配置与受控样本fifo-自检)，不在这里再复制一套步骤。

## 换电脑与打包

接收方自行核对领航者V2/7020的具体修订、供电、JTAG、USB_UART及AMD工具/驱动。使用无空格英文路径和本机实际安装目录/COM号，115200、8N1、无流控。工作区在接收方生成，不能整包复制原电脑缓存；创建后不要移动。默认工具路线为2026.1，其他版本兼容性另核。

从项目根目录制作新的候选包并离线核对：

```powershell
python -B board/package_ecg_smoke.py --output-dir tmp/ecg_smoke_kit_new
python -B sim/check_smoke_handoff.py tmp/ecg_smoke_kit_new.zip
```

输出必须是新的tmp目录，已有目标即停止。打包器检查固定的核心组合哈希；源码/产物改变时须重新构建验证，不绕过检查。候选包不能自动替换latest或继承板上通过结果。

完整解压后按包内README操作：预编译入口为board/run_smoke.ps1；GUI路线先用board/create_workspace.ps1在接收方生成工作区，再在Vitis选择ecg_smoke运行。工具位置通过-VitisBin传入，具体命令见包内说明。每次运行需要系统复位并重新配置PL，避免旧FIFO状态影响。

## 如何判定通过

先打开实际串口再运行。保存从BEGIN到结尾的完整文本，最终出现`PASS ECG_SMOKE failures=0`且中间没有FAIL才算通过；JTAG脚本启动成功、构建成功或只看到Hello World都不能替代。保存工具/板卡版本、输入和匹配文件清单；失败保留原日志，不反复复位覆盖现象。串口采集辅助脚本按latest说明使用，其实际验证范围单独记录。

## 记录入口

- [板上通过证据](records/smoke_board_validation_20261017.md)：原始报告、UART和核验依据，保留原字节。
- [交接与发布合并记录](records/smoke_release_20261017.md)：离线重建、失败修正、旧版归档、发布检查及各阶段边界。

使用方法在本文/下载教程/latest说明维护，实验输出只记docs/records/；不在多个使用说明里重复更新验收流水。
