# 三核心电演示交付：FP32 CNN、INT8 CNN、HGB

本目录是2026-11-03已板测的匹配JTAG组合。原CNN整段/实时、HGB整段保留，新增INT8整段/实时与同拍量化对比。工具版本Vivado/Vitis 2026.1，器件xc7z020clg400-2，实物正点原子领航者V2。不是QSPI包，不与旧releases/latest交叉替换。

## 克隆后直接运行

在仓库根执行；使用英文工作路径。需要Python 3.13、Node 22、Vitis 2026.1及USB串口驱动。

```powershell
python -B board/cnn_triple_20261103/check.py
python -m venv tmp/web_env
& tmp/web_env/Scripts/python.exe -m pip install -r src/web/requirements-lock.txt
& build/build_web.ps1
```

连接对应板卡电源、JTAG、USB_UART，按[下载教程](../../docs/download_guide.md)核实启动方式和连线；关闭串口监视器。启动Vitis的hw_server（端口3121）。JTAG序列号可在xsdb中connect后执行`targets`核实；USB身份可先运行网页，在串口下拉列表查看。不要照抄其他电脑的COM口/电缆号。

下面命令会复位目标并临时加载BIT/ELF，不写Flash；output使用不存在的tmp子目录：

```powershell
& tmp/web_env/Scripts/python.exe board/cnn_triple_20261103/load.py --xsdb '<Vitis>/bin/xsdb.bat' --cable '<实际JTAG序列号>' --port '<实际COM口>' --device-id '<网页枚举的device_id>' --output tmp/triple_load_new
& tmp/web_env/Scripts/python.exe src/web/run.py --port 8000
```

打开http://127.0.0.1:8000，首次账号按[统一教程](../../docs/download_guide.md)创建。进入“检测与加速”，选择实际板卡串口，使用CSV回放或ADS采集。CNN可选FP32/INT8、整段/实时；HGB保留整段。真实采集需另选ADS接收器串口。不同配置新建会话，正常结束后无需复位。断电后重新JTAG加载。

不依赖私人数据的演示：选择文件回放，使用仓库内`data/cnn_triple_synthetic500.csv`（60秒合成信号，明确不是人体数据），勾选按采样节拍回放，选CNN实时和INT8。ARM/FPGA及量化面板随有效拍更新，停止后保存累计时间。再分别选择FP32、HGB整段验证原功能。真实无线并发、长时、带标注分类精度及Flash冷启动不在本组合已验范围。

## Vivado资源及芯片布局页面

无需板卡。在Vivado 2026.1的Tcl Console执行，路径换成自己的克隆目录：

```tcl
source {<仓库绝对路径>/board/cnn_triple_20261103/open_routed.tcl}
```

脚本打开原始routed.dcp，并生成系统资源、CNN层级与时序报告。Device视图可看真实实现布局；ecg_cnn_0为FP32，ecg_cnn_int8_0为INT8。DCP是原实现设计快照，修改算法应走下一节完整重建。各核并行度不同，不能把性能变化全部归因于位宽。

## 修改与重建硬件工程

硬件工程的完整输入在`src/rtl/`、`src/hls/ecg_cnn/`、`src/hls/ecg_cnn_int8/`、`build/build_navigator_ecg_system.tcl`、`build/build_cnn_int8_pl.tcl`，权重在`model/`，ARM在`src/ps/ecg_cnn/`。这些随Git上传；不复制引用原作者绝对路径的缓存XPR。

准备含PyTorch/NumPy/SciPy的Python环境，使用本目录`requirements-model.txt`（本轮实际CPU环境；PyTorch CPU包可指定官方CPU索引）。然后执行统一重建入口（不连接板卡、不自动下载）：

```powershell
& build/rebuild_cnn_triple.ps1 -Python '<模型环境python.exe>' -Vitis '<Vitis绝对目录>' -Vivado '<Vivado绝对目录>' -Name triple_rebuild_01
```

此入口依次导出HGB/FP32/INT8参数、HLS综合和RTL联合仿真、系统综合/布局布线/时序检查、生成BIT/XSA并重建ARM。完成后在Vivado打开`tmp/triple_rebuild_01/hardware/cnn_pl.xpr`，可编辑BD、重综合。Vitis输出位于同名tmp目录的vitis子目录。首次构建较慢，需要足够内存和磁盘。重建步骤由本机已验证的分阶段入口串联；该统一入口本轮仅语法检查，未重新完整综合，不承诺跨主机/工具补丁得到逐字节相同BIT或完全相同计时。

直接运行使用本目录原字节产物，可由manifest校验一致；改源码后不能继续声称与旧封印匹配。原始构建收据保留历史路径，load.py只生成本次克隆的派生清单，不修改原收据。

第三方边界沿用[许可说明](../../docs/licenses.md)。AMD IP及工具生成产物适用其各自条款，项目MIT不替代供应商许可。未上传工具安装、患者记录、账户数据库或工程缓存。
