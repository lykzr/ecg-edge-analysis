# ECG Edge

基于 Zynq-7020 的单导联心电边缘分析原型，用于研究 ECG 数据的软硬件协同处理、QRS 检测与 RR 间期计算。

项目以公开心电数据回放为起点，在软件侧建立参考算法，在 FPGA 侧实现采样处理和事件接口，通过 PS 读取与管理检测结果。目标平台为**正点原子领航者 V2**，器件为 `xc7z020clg400-2`。

项目正在开发中：候选峰算法目前为软件原型，尚未移植到 RTL；**ECG smoke 尚未上板测试**。本项目用于教学与工程验证，不作为临床诊断设备。

## 项目组成

- **软件参考**：ECG 数据读取、整数幅值转换、启动校准、QRS 候选峰检测与标注评估；另保留与现有 RTL 对应的逐周期模型。
- **PL 处理接口**：基础 QRS 候选检测、AXI-Lite 寄存器和事件 FIFO，提供检测位置、RR、队列及溢出状态。
- **PS 自检应用**：发送受控样本，检查配置、事件读出与 FIFO 行为。
- **开发工具**：工程生成脚本、软件/RTL 对照、接口仿真及数据评估工具。

当前数据输入来自公开记录或 PS 生成的合成样本。真实 AFE/ADC 采集尚未接入。

## 目录

| 目录 | 内容 |
| --- | --- |
| `src/rtl/` | FPGA 检测器及 AXI-Lite 接口 |
| `src/ps/` | PS 端应用 |
| `src/reference/` | 软件参考模型与输入处理 |
| `sim/` | testbench、自检和软件/RTL 对照 |
| `build/` | Vivado 配置与工程生成脚本 |
| `board/` | PS 构建、下载与串口操作说明 |
| `data/` | 数据获取、评估脚本与参考结果 |
| `skill/` | 可复用的开发与排错流程 |
| `report/` | 项目计划与报告材料 |
| `docs/` | 接口、教程、实验记录与报告素材 |
| `releases/latest/` | 当前发布包及配套说明 |
| `tmp/` | 本地构建工作区、日志和缓存，不纳入交付 |

## 快速开始

所有命令均从项目根目录执行。

### 运行软件参考算法

当前入口为v4，需隔离Python环境及WFDB，完整安装/下载步骤见[数据使用说明](data/README.md)。已有环境和原始数据时：

```powershell
& './tmp/qrs_env/Scripts/python.exe' -B data/benchmark_qrs_v4.py --raw-dir tmp/qrs_current/raw --output-dir tmp/qrs_current/development --models v4
```

输出目录必须不存在。历史算法与实验入口归档于tmp/history/qrs_20261016，正式目录保留当前实现与必要公共依赖。

### 创建硬件工程

使用 Vivado 2026.1，在命令中替换工具安装路径：

```powershell
& '<Vivado安装目录>/bin/vivado.bat' -mode batch -source build/create_rtl_project.tcl -tclargs xc7z020clg400-2
```

默认在 `tmp/vivado/ecg_edge` 创建工程，已有目录时停止。此步骤创建 PS7/AXI Block Design 并生成工程输出；后续综合、实现、导出与 PS 程序运行见 [构建入口](build/README.md) 和 [下载教程](docs/download_guide.md)。

## 文档导航

- [工程文档与报告素材](docs/README.md)

- [项目计划与开发优先级](report/project_plan.md)
- [板上运行、smoke 与串口教程](docs/download_guide.md#20-ps-读取配置与受控样本fifo-自检)
- [寄存器接口](docs/register_map.md)
- [仿真与软件测试](sim/README.md)
- [数据、评估方法与结果](data/README.md)
- [当前发布包说明](releases/latest/README.md)
- [可复用流程](skill/README.md)

## 许可证

项目自有代码与文档采用 [MIT License](LICENSE)。第三方数据、工具生成内容及参考资料按各自许可使用，详见 [第三方来源说明](third_party.md)。
