# ARM分类接口自检

本应用在领航者V2 Zynq-7020 ARM核0测试已准备张量/队列，包含受控时钟的超时与复位测试。它不接QRS/AXI或CNN，不是临床或算法准确性演示。

## 构建

从项目根运行，使用已有Vitis，不安装依赖。脚本核对当前latest/smoke匹配硬件清单，创建新的tmp工作区，默认目录已存在时拒绝覆盖；可用ECG_CLASS_WORKSPACE指定新的项目tmp英文目录。

```powershell
& '<Vitis>/bin/vitis.bat' -s board/build_classification.py
```

产物build_manifest.json含本次构建ID、源码及bit/XSA/init/ELF的字节数和SHA256。

## 临时JTAG验证

仅在已获实物操作授权且确认唯一板卡/下载器及实际USB实例后执行。已有hw_server需要在本机3121端口就绪，其他串口终端先关闭。验证脚本核身份和SHA，先开串口再复位/配置PL/下载新ELF，不写Flash。参数按当前枚举结果填写，不能复制某成员COM号。

```powershell
python -B board/verify_classification.py --manifest <项目tmp工作区/build_manifest.json> --xsdb <Vitis/bin/xsdb.bat> --cable <实际JTAG序列号> --port <实际COM> --device-id '<实际USB实例>' --output tmp/class_board_new
```

完整7项PASS和本次build_id对应的PASS ECG_CLASS_INTERFACE failures=0才通过；输出和错误保存在新目录，不自动重试/复位覆盖现象。详细输入与待验边界见[分类接口](../../../docs/classification_protocol.md)，实际运行证据集中[记录](../../../docs/records/classification_20261023.md)。
