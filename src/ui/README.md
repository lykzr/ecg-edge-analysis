# 电脑界面

本目录只放Tk窗口、界面状态与共享绘图。协议、串口、采集/中转后台和记录逻辑在[PC后台](../pc/README.md)，板卡构建与下载脚本在board/，板端C源码在src/ps/。

从项目根启动：

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B src/ui/main.py
```

也可用已安装的Python3.10以上版本；界面需要Tkinter。入口按自身位置定位项目，支持从其他工作目录使用绝对路径启动。旧src/pc/ecg_monitor.py无参数启动仍兼容，无界面命令行继续使用该旧入口。

| 文件 | 职责 |
| --- | --- |
| main.py | 统一启动入口，建立模块搜索路径并转交参数 |
| monitor.py | 主监视器、状态卡片、结果波形、事件与诊断 |
| capture.py | 厂商CSV与蓝牙采集窗口 |
| bridge.py | CSV/蓝牙送样与Zynq回传窗口 |
| plot.py | 共用绘图几何、Canvas绘制和SVG导出；导入时不需要Tk |

窗口互斥和后台生命周期不因分目录改变；点击连接才打开所选串口，不自动探测/复位板卡。来源原码与回传int16单位分开，未提供的滤波或类别仍显示未知。源数据和记录留tmp/，不保存在本目录。完整操作见[客户端教程](../../docs/pc_monitor.md)和[中转教程](../../docs/bridge.md)。
