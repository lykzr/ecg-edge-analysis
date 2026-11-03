# CNN候选工程交接

此目录保留早期封印，以下INT8未完成状态仅对应本目录旧候选。当前已板测三核版本使用[新交付](../cnn_triple_20261103/README.md)，不要混用。

此目录从最后通过实板验证的临时工程提取匹配镜像，便于队友直接检查和临时运行。原临时工程保留在原地，未移动、未删除。这里不是新的Flash发布，未替换 `releases/latest`。

| 目录 | 内容及状态 |
| --- | --- |
| `fp32/` | H27 fold0 FP32 CNN与HGB同一PL镜像；CNN实时/整段及HGB整段。BIT、XSA、ELF、链接图、FSBL、PS初始化Tcl及原构建收据 |
| `int8_candidate/` | 动态W8A8参数、12组合成输入及预期输出、导出信息；是待验证候选，不能与FP32镜像混用 |
| `manifest.json` | 新旧路径映射、文件长度、SHA256、来源提交及状态 |
| `check.py` | 只用Python标准库进行离线完整性校验 |

## 检查与临时运行FP32

从仓库根执行：

```powershell
python -B board/cnn_demo_20261103/check.py
```

校验通过只表示文件完整。原构建收据仍写 `ECG-DUAL-1`；保持其原字节，新清单依据[流式实测证据](../../docs/evidence/cnn_stream_20261102.json)注明实际支持 `ECG-DUAL-STREAM-1`，没有回写旧收据。

需要运行时，先核实实物为领航者V2 Zynq-7020，连接供电、JTAG和USB_UART，关闭网页采集/串口监视器，启动对应工具的hw_server（3121）。下列命令会复位并临时加载板卡，不写Flash；此交接整理没有执行它。替换工具路径和实际JTAG序列号，不直接沿用某成员的COM口或电缆号。

```powershell
$vitis = '<Vitis安装目录>'
$demo = Join-Path $PWD 'board/cnn_demo_20261103'
python -B "$demo/check.py"
if ($LASTEXITCODE -ne 0) { throw '镜像检查失败，停止下载' }
& "$vitis/bin/xsdb.bat" board/hgb_handoff/load.tcl '<实际JTAG序列号>' "$demo/fp32/cnn_pl.bit" "$demo/fp32/ps7_init.tcl" "$demo/fp32/ecg_cnn_arm.elf"
if ($LASTEXITCODE -ne 0) { throw 'JTAG启动失败' }
```

Tcl会检查电缆唯一且存在xc7z020/Cortex-A9核。下载完成需另行核对串口READY及网页推理；JTAG启动成功不等于推理验收。然后按[统一教程](../../docs/download_guide.md#新增cnn实时模式保留两种整段模式)启动原前后端，选实际USB_UART，使用CNN实时、CNN整段或HGB整段功能。FSBL仅保留配套来源，不在上述JTAG命令中使用。本目录不包含BOOT.BIN。

## 修改与重建

完整本地Vivado工程是 `tmp/cnn_pl_build_01/cnn_pl.xpr`，Vitis工程是 `tmp/cnn_stream_vitis_01/`；HLS工程是 `tmp/cnn_hls_07/`。它们含工具缓存和本机绝对路径，仅留本地。XPR还引用工程外HLS IP，单独复制XPR不能作为可移植工程。

可重建源码和正式脚本已在本Git分支中，源码基准见清单的 `fp32.source_commit`。要复现原FP32版，使用该提交的源码，在新输出目录按[从源码重建双模型候选](../../docs/download_guide.md#从源码重建双模型候选)操作；不启用 `ECG_CNN_INT8`。更改硬件/权重后重新生成匹配BIT、XSA、ELF与收据，不能继续宣称匹配本目录封印。原构建收据的tmp路径是历史来源，不是克隆后运行本目录镜像的依赖。

INT8入口为 `build/export_cnn_int8.py`、`build/run_cnn_int8_hls.ps1`、`sim/check_cnn_int8.py`，核心在 `src/hls/ecg_cnn_int8/`，Python参考在 `model/cnn_fourclass/int8_reference.py`。参数可重新导出到新tmp目录；运行脚本需显式传入本机工具和参数位置。

这是W8A8权重/激活、INT32乘加、FP32缩放/残差/偏置的混合精度实现，使用逐输入动态二次幂缩放，未重训、未用患者数据校准。原生C++/Python对照记录保留在 `int8_candidate/host_check_original.json`；合成样例一致率不能当患者分类准确率。INT8还需完成RTL联合仿真、系统实现、板测、真实精度及性能/资源比较和前后端接入。本目录没有INT8可运行BIT/ELF，也没有承诺量化加速倍数。INT8卷积并行度与原FP32不同，未来比较应同时说明位宽及并行度。

镜像及运行库的第三方边界沿用[许可说明](../../docs/licenses.md)、[第三方说明](../../third_party.md)和仓库保留的原文；自有MIT许可不替代AMD IP、BSP和工具链运行库各自条款。
