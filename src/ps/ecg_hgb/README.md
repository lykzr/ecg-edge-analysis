# HGB的Zynq ARM移植核心

依据`model/inference`的v92/fold0冻结输入与权重，实现可移植C11整段流水线。保留500Hz、单导联mV、hp05/raw、4096单位/mV、128点波形及192维特征。N/S/VF中的VF为V/E/F合并，不是心室颤动。当前仍是未全部达标的研究模型，不重新训练、不量化。

## 接口

- `HgbInput`清零开启新会话；`ecg_hgb_input`将mV分块高通/量化为int16，同会话持续保留状态。已匹配高通用`highpass=0`，未高通用1；已开始后切模式拒绝，须新会话。缺样、重连、导联/增益切换均由应用开启新会话，不自动插值。
- `ecg_hgb_workspace_size(samples)`返回整段检测与重切拍的工作区大小，`ecg_hgb_prepare`消费完整int16记录，生成冻结模型自己的定位、窗口和RR请求。工作区由调用者持有且8字节对齐；无内部malloc。不能把现有板端原窗口直接当作重切拍结果。
- `ecg_hgb_record`消费以上请求并计算完整历史背景、后继RR、节律、Hermite及树推理。结果携带原编号、位置、决定时刻、状态、192项特征及概率。无效拍`class_id=-1`、概率为NaN，序列化时转换成未知/null，不能强制算N。
- `ecg_hgb_probability`仅用于已生成的192维特征，不接收原始波形。

输入、请求、输出和工作区使用独立、不重叠的缓冲区。样本数1—1800000，事件数上限30000，容量不足明确报错；调用失败后不可当成完整结果。调用者负责根据可用DDR选择更小的实际上限，并在分配前检查容量。整段工作区、请求、结果仍随长度增长，不是实时环形缓存实现。首RR未知、末端窗口不足、下一拍等待上限1250点和记录结束行为保持原定义。

## 重建与离线对照

使用已有NumPy/SciPy与GCC环境，从仓库根运行；输出目录必须不存在：

```powershell
python -B sim/check_hgb_arm.py --output tmp/hgb_host_new
python -B build/build_hgb_arm.py --cc '<已有工具链>/bin/arm-none-eabi-gcc.exe' --output tmp/hgb_arm_new
```

第一条编译实际主机C并与冻结Python/原生参考逐项比较。第二条生成Cortex-A9/VFPv3/hard-float的`libecg_hgb.a`，保留对象、编译命令、源码/参数哈希、ELF32 ARM检查和栈用量。参数由`build/export_hgb.py`确定性生成；不把生成常量和编译缓存放进正式源码。

新实现使用`-ffp-contract=off -fno-fast-math`，阈值/叶值保持double，特征在原有边界转float32。不要未经验证启用快速数学、改float或INT8。交叉编译与目标执行分别检查，实际证据集中在当前报告。

冻结原生源从`model/inference/native`直接只读编译。构建强制包含`frozen.h`，将其内部函数改名为`hgb_frozen_*`，不与当前固件的同名QRS、切拍和分类队列符号混用。不能省略该构建选项。导出常量/库和所有日志留tmp；既有固件和release不替换。

## 独立板端应用

`board_test.c`提供固定受控输入的ARM自检，`main.c`提供双协议应用：原`ECG-IN-1/ECG-UART-1`实时QRS与新增`HGB-BATCH-1`整段分类。两者从当前已验smoke硬件建立Vitis裸机平台，不改变PS7/MIO/DDR配置。默认构建自检；双协议使用`ECG_HGB_APP=batch`。输出目录必须为新目录，依赖现有Vitis 2026.1、NumPy/SciPy和ARM GCC，不安装软件。

```powershell
$env:ECG_HGB_WORKSPACE = '<仓库绝对路径>/tmp/hgb_batch_new'
$env:ECG_HGB_APP = 'batch'
$env:ECG_ARM_GCC = '<工具链目录>/bin/arm-none-eabi-gcc.exe'
& '<Vitis目录>/bin/vitis.bat' -s board/build_hgb_test.py
```

自检先运行`python -B board/prepare_hgb_test.py --output tmp/hgb_fixture_new`，设置`ECG_HGB_APP=test`与`ECG_HGB_FIXTURE`为该目录绝对路径后构建。生成清单核对源码和bit/XSA/init/ELF的长度及SHA；目标ARM使用hard-float、256KB栈及静态DDR缓冲区。批处理上限30000点、480拍，超限拒绝，不截断。它先接收完整记录再检测、重切拍和分类，不是持续实时环形推理。

获得当前临时下载授权并核对唯一板卡后，用`board/load_hgb.py --manifest <build_manifest.json> --xsdb <xsdb.bat> --cable <下载器序号> --port <端口> --device-id <USB身份> --output <新目录>`下载批处理。自检用`board/run_hgb_test.py`（参数见`--help`），随后`board/verify_hgb_test.py`核对真实DDR与冻结参考。脚本系统复位时保持停止，再初始化与下载，避免旧QSPI程序先运行；均不写Flash。

电脑端运行`python -B src/pc/ecg_hgb.py --input-mv <单列无表头mV文件> --preprocess hp05 --port <端口> --device-id <USB身份> --output <新目录>`。原始mV用hp05，严格匹配高通后的数据才用raw。`board/verify_hgb_uart.py --directory <结果目录> --input-mv <相同输入>`重新调用冻结参考核对。协议与故障检查见`docs/protocols.md`、`board/check_hgb_uart_faults.py --help`。不得向未核对身份的采集端发送命令。

双协议通过`legacy.c`复用原实时源码，单独编译为`libhgb_legacy.a`，避免模型冻结检测器与正式QRS的同名符号混用。空闲广播原实时就绪头，收到HGB握手才宣布模型身份；同一时刻只执行一种会话，不交错报文。正常结束可切换模式，错误停止规则以各自协议为准。网页勾选“Zynq ARM整段分类”使用新协议，取消后保留原实时心率。该模型仍是整段收齐后运算，不提供连续分类；ARM执行不代表FPGA PL推理。

`board/check_hgb_web.py --port <串口> --device-id <USB身份> --output <新tmp目录>`显式操作实板，依次验证模型、原实时QRS、厂商格式模型回放，不复位，不写Flash；它不是无硬件单元测试。`board/prepare_hgb_qspi.py --manifest <构建清单> --bootgen <bootgen.bat> --output <新tmp目录>`核对同源FSBL/bit/ELF并生成QSPI候选，不自动写板。编程、复位和冷启动必须另验，步骤见[统一教程](../../../docs/download_guide.md)。

本次Cortex-A9编译报告的`ecg_hgb_prepare`单函数栈帧约20KB，且会嵌套调用原检测器；不能沿用未经核对的8KB默认栈。最终栈峰值、DDR总量、每拍耗时和500Hz持续处理能力仍须在实际应用中测量。

来源、权重与研究边界沿用`model/inference/provenance.json`和原许可。冻结检测代码派生WFDB，继续保留`model/inference/licenses/wfdb_license.txt`；自有C移植遵循项目MIT许可。
