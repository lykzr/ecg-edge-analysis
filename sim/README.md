# 检查与回归

从仓库根运行，使用已有Python环境。检查不安装依赖、不训练、不操作板卡，也不创建提交副本或压缩包。临时日志放tmp/，正式发布证据放docs/evidence/，开发过程记录留在被忽略的docs/records/。

## 提交前检查

```powershell
python -B sim/check_repository.py
python -B sim/check_checkout.py
python -B sim/check_system_release.py
```

check_repository读取实际Git索引，拒绝本地资料混入、已跟踪但被忽略、必需文件漏跟踪及Markdown文件链接失效。新增正式文件须加入Git跟踪后再检查；加入索引不等于提交。该检查不核对远端，不检查Markdown标题锚点或外网URL。

check_checkout核对必要文件、Python语法/局部导入、Vivado工程来源和冻结基线哈希。check_system_release核对当前匹配镜像、源码身份和既有实板证据；不得把离线核对称作再次上板。原始收据内部保留历史路径，由发布检查映射至docs/evidence/读取。

## 针对性回归

```powershell
python -B -m unittest discover -s sim -p test_repository.py
python -B -m unittest discover -s sim -p test_checkout.py
python -B -m unittest discover -s sim -p test_system_release.py
python -B -m unittest discover -s sim -p test_qspi_release.py
python -B -m unittest discover -s sim -p test_runtime_sessions.py
```

仓库检查回归覆盖漏跟踪、失效链接和本地资料误跟踪；发布回归覆盖路径边界、文件篡改、源码漂移、便携启动及精确忽略规则；会话回归覆盖正常结束后的状态重置与故障停止。测试输出才是本次实际结果，本文不累计成绩。

通信/软件运行时的完整离线回归：

```powershell
python -B sim/check_system_offline.py --output tmp/offline_new
```

输出目录必须不存在；直接检查当前仓库，使用已有NumPy/SciPy/WFDB、主机C编译器及Tk环境。检查会编译主机C对照并产生测试日志，但不构建新的FPGA镜像。具体依赖见data/requirements_qrs.txt，网页依赖见src/web/requirements-lock.txt。

独立INT8算子、训练参考及数据评估脚本仍按自身参数使用，不表示最终模型或PL整网已部署。板端下载与源码重建统一见[使用教程](../docs/download_guide.md)，当前报文见[协议](../docs/protocols.md)，实际系统分工与缺项见[当前实现与缺项](../report/report.md)。
