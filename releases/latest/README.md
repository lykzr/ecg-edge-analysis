# 当前发布：Hello World / QSPI

版本：`20261013-hello-world-qspi-v1`。工具：Vivado/Vitis/Bootgen 2026.1。适用板卡：正点原子领航者 V2，Zynq-7020；具体核心板和底板修订尚未独立核实。本镜像运行 Hello World，不执行 ECG 送样或检测。

硬件与软件构建、镜像头检查通过。用户已提供 Flash 校验成功和 PS 复位后 COM14/115200 应用输出；完整断电再上电过程尚未单独确认。证据摘要见 [validation.md](validation.md)，文件来源、大小、SHA256 见 [artifacts.json](artifacts.json)。

## 烧录

先确认是否替换原有 QSPI 引导内容，写入 offset 0 会覆盖它。断电设置领航者 BOOT_CFG 1=ON、2=ON（JTAG），连接下载器后上电。在 Vitis → Program Flash 中选择：

| 字段 | 内容 |
| --- | --- |
| Image File | 本目录 `BOOT.BIN` |
| Offset | `0x0` |
| Flash Type | `qspi-x4-single`（2026.1 界面名称） |
| Init File | 本目录 `fsbl.elf` |
| Verify after flash | 勾选 |

如果图形界面无法在安装目录创建临时文件，可在 PowerShell 切换到本目录后调用工具；替换安装路径占位符：

```powershell
& '<Vitis安装目录>/bin/program_flash.bat' -f './BOOT.BIN' -fsbl './fsbl.elf' -offset 0x0 -flash_type qspi-x4-single -verify -url TCP:127.0.0.1:3121
```

编程与校验成功后，断电切换 BOOT_CFG 为 1=ON、2=OFF（QSPI），打开 115200 串口再上电，不点击 Run。已处于 QSPI 模式时，重看一次打印可按 PS 复位键。预期输出：

```text
Hello World
Successfully ran Hello World application
```

## 文件与复现

`BOOT.BIN` 是可直接烧录镜像，`fsbl.elf` 是烧录初始化文件；保留匹配 bit/XSA/应用 ELF 便于诊断和重建软件平台。`boot.bif` 引用均在本目录内，运行 Bootgen 前切到本目录。重新打包时输出到新的文件名，核对后再按归档规则更新 latest，不能把重新打包当已实测。

源码与构建配置在项目正式目录，哈希记录在清单；原始构建及完整日志保留在 `tmp/qspi_boot_20261013_01/`。镜像不依赖该 tmp 路径进行烧录。新版本替换 latest 前先将旧 latest 可恢复地归档到 `releases/history/<版本>/`；历史仅保存在本地并被忽略，不删除。
