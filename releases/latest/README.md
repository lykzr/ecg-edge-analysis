# ECG 系统 JTAG 烧录产物

本目录只放 **Vivado/Vitis JTAG 烧录所需文件**，不重复存放源码、文档或证据。

```
releases/latest/
├── README.md
├── LICENSE
├── third_party.md
├── manifest.json
├── artifacts.json
├── smoke/
│   ├── hardware/{ecg_system_candidate.bit, .xsa, ps7_init.tcl}
│   ├── prebuilt/ecg_smoke.elf
│   ├── run_smoke.tcl
│   └── manifest.json
└── bridge/
    ├── hardware/{ecg_system_candidate.bit, .xsa, ps7_init.tcl}
    ├── prebuilt/ecg_bridge.elf
    ├── run_bridge.tcl
    └── manifest.json
```

## 使用

- JTAG 临时运行：Vivado Hardware Manager 连接开发板，按 `smoke/run_smoke.tcl` 或 `bridge/run_bridge.tcl` 的步骤加载 `ps7_init.tcl`、bitstream 和 ELF。
- 本包 **没有写 Flash**；掉电保存需另行打包 BOOT.BIN 并确认启动方式。
- 证据在仓库 `docs/records/`：smoke 实板记录、bridge 有限数字回放记录；`artifacts.json` 的 `evidence` 字段给出对应路径和 SHA256。
- 源码、构建脚本和完整说明在仓库 `src/`、`board/`、`build/`、`docs/`，不在本目录重复。
- 两个硬件镜像不同；不要混用 smoke 与 bridge 的 bit/xsa/ELF。
