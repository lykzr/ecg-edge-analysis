# 发布与历史归档

当前本地交付入口为[系统JTAG包](latest/README.md)：只放独立smoke、旧500Hz中转和新500Hz ARM运行时的 **JTAG烧录产物**（bit/XSA/ps7_init/ELF/run 脚本），源码、文档和证据留在仓库。每个组件各有匹配bit/XSA/ELF，不能交叉使用；没有 BOOT.BIN 或 QSPI 固化。真实无线、人工界面和算法/CNN 仍按实际验收范围说明。

```text
releases/
  README.md
  latest/
    README.md
    LICENSE / third_party.md
    manifest.json            本包文件/字节/SHA256
    artifacts.json           构建来源、源码哈希、证据路径与验收边界
    smoke/
      hardware/              bit/XSA/ps7_init
      prebuilt/ecg_smoke.elf
      run_smoke.tcl
      manifest.json
    bridge/
      hardware/              bit/XSA/ps7_init
      prebuilt/ecg_bridge.elf
      run_bridge.tcl
      manifest.json
    runtime500/              新ARM匹配硬件/ELF/清单及download.cmd、run_runtime500.ps1/tcl
  history/<版本>/            旧版原字节保留，本地忽略
```

旧 Hello World/QSPI 在 `history/20261013-hello-world-qspi-v1`，旧独立 smoke 在 `history/20261017-ecg-smoke-jtag-v1`。历史清单和文件不覆盖、不删除；派生 Vivado/Vitis 工程仍在 tmp。当前包使用方式见 latest 说明；源码与构建脚本在仓库 `src/`、`board/`、`build/`，验收记录在 `docs/records/`，不复制进发布包。归档/校验证据见[发布记录](../docs/records/system_release_20261021.md)。

## 替换与核验

1. 从同一匹配构建复制必要硬件、ELF 和 run 脚本；不复制源码、文档、证据或工具缓存。
2. 先在 tmp 生成候选，核对 SHA256、XSA 内嵌 bit、ELF 头和实际验收；待验证功能不能冒充已通过。
3. 得到当前发布授权后，先确认源/目标在项目内且 history 版本不存在，再完整归档旧 latest 并核验每个文件；不覆盖历史。
4. 放入新 latest，核对文件清单、嵌套清单和便携入口。JTAG 启动、算法准确率、真实无线、人工显示和掉电保存分别验收。
5. 更新 .gitignore 只放行本说明与 latest 精简文件；其他历史和运行产物忽略但保留。

离线核验：`python -B sim/check_system_release.py --directory releases/latest --repository .`；smoke 单独运行 `python -B sim/check_smoke_release.py --directory releases/latest/smoke --repository .`。这两个脚本只校验发布产物，并在仓库中核对源码哈希与证据；不连接板卡。

本地发布目录不代表 Git 提交、推送或远端上传。已跟踪旧文件不会因增加忽略规则自动取消跟踪；索引调整需本会话另行授权。历史、缓存和用户数据不自动清理。

当前runtime500同时支持标准数字输入与客户端归一化后的厂商ADC输入，默认双击[download.cmd](latest/runtime500/download.cmd)，其PowerShell入口先核对包内SHA再临时下载。旧bridge仅供legacy500回归；完整操作见[下载教程](../docs/download_guide.md)。旧latest原字节归档到history中对应版本，不覆盖历史。当前验收边界和发布过程见[记录](../docs/records/runtime500_release_20261025.md)，真实无线/标定、最终CNN和Flash仍单独验收。

## 当前交接与掉电运行

当前500Hz应用已固化到本机板卡QSPI。已写同版镜像时直接QSPI上电，有限会话结束后PS复位；另一块板卡先核对匹配组合，按docs/download_guide.md的QSPI入口操作。JTAG仍是临时下载。完整未完成项统一见report/交接.md，验收见docs/records/qspi_20261025.md；不将数字CSV回放当真实无线、标定或CNN完成。路径均相对仓库根。
