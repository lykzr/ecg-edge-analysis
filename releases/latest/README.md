# ECG 系统预编译硬件文件

本目录仅保存预编译的硬件文件和运行脚本，不重复存放源代码。

## 目录结构

```
releases/latest/
├── README.md                    # 本说明文件
├── artifacts.json               # 构建产物清单
├── manifest.json                # 发布包清单
├── smoke/                       # Smoke 测试预编译文件
│   ├── hardware/               # 360Hz 自检硬件
│   │   ├── ecg_system_candidate.bit
│   │   ├── ecg_system_candidate.xsa
│   │   └── ps7_init.tcl
│   ├── prebuilt/               # 预编译 ELF
│   │   └── ecg_smoke.elf
│   └── run_smoke.tcl           # JTAG 启动脚本
└── bridge/                      # Bridge 中转预编译文件
    ├── hardware/               # 500Hz 中转硬件
    │   ├── ecg_system_candidate.bit
    │   ├── ecg_system_candidate.xsa
    │   └── ps7_init.tcl
    ├── prebuilt/               # 预编译 ELF
    │   └── ecg_bridge.elf
    └── run_bridge.tcl          # JTAG 启动脚本
```

## 使用方法

### Smoke 测试
```powershell
cd smoke
# 使用 board/run_smoke.ps1 脚本（需从项目根目录 board/ 获取）
```

### Bridge 中转
```powershell
cd bridge
# 使用 board/run_bridge.ps1 脚本（需从项目根目录 board/ 获取）
```

## 说明

- **源代码位置**：所有源码在项目根目录的 `src/`, `board/`, `build/` 等目录中
- **构建脚本**：使用 `board/` 目录下的构建脚本重新生成这些文件
- **验证记录**：详见项目根目录 `docs/records/` 中的验证文档
- **完整文档**：参见项目根目录 `docs/download_guide.md`

## 文件来源

这些文件由以下构建生成：
- 硬件：通过 `build/build_navigator_ecg_system.tcl` 生成
- 软件：通过 `board/build_ecg_smoke.py` 和 `board/build_ecg_bridge.py` 生成

详细构建记录见 `artifacts.json` 和 `manifest.json`。
