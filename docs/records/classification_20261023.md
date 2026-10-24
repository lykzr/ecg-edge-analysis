# 分类接口与系统集成记录

## 目标与环境

按2026-10-23 23:40一次定时任务，先完成ECG-CLASS-1及离线系统准备，再按用户新授权核对板卡做临时JTAG。QRS/训练暂停，不读独立6人，不改PS7/MIO/供电/Flash/Git/当前发布。Windows11、Python3.14.7；已有QRS环境NumPy/SciPy/WFDB与Torch CPU环境分开使用；不安装依赖。

## 依据与修改

对照BeatWindow.model_input、common_window/causal_rr、train_cnn_cv.tensors、模型内部waveform_channels及PC旧解析器。原窗口只给basicRR，本轮另补同一权重rr_mean/std的float32变换和[-5,5]裁剪；保持原窗口/QRS数学定义。128波形+RR3、模型/预处理/归一化SHA、N/S/V/F顺序、首RR/短窗未知、队列满、超时/迟到、会话复位均有明确出口。

新增src/reference/ecg_classifier.py、src/ps/ecg_classification和data/replay_classification.py。C层只管理已准备好的张量，RR变换与Python按1e-6核验；不含波形重采样/QRS/CNN算子，不能当完整上板移植。E选择完成后一次发送，沿原evt，不修改现有ECG-UART-1字段/解析器，不与厂商34字节或ECG-IN-1混合。无效类别?/置信度-1，不填正常N。

## 实际检查与失败保留

- Python接口13项、实际C核心6项、Torch3项通过。Torch检查训练函数变换逐值一致及直接模型/适配器输出一致，未训练。
- 现有通信/显示回归：bridge19、PC核心14、串口16、采集20、窗口5、逐样本运行时7项通过；本机Tk隐藏窗口用例本次实际执行，不等于人工视觉验收。
- 最初GCC写系统TEMP失败，已改测试子进程TMP/TEMP为本次独立项目目录，后续编译通过；首次compile.log留tmp。一次test_classif*.py在无Torch的QRS环境误导入Torch测试失败，原日志tests_qrs.log保留，改为各环境单独运行，通过日志独立保留。
- 第一次逐文件回放比较漏生成SVG导致FileNotFoundError；补生成回放SVG后7文件一致，未覆盖原记录。

## 公开记录软件闭环

100号前30秒，10800样本、35事件/35结果，1个首RR未知，34个有效开发分类结果。只加载model/baseline/residual_verified/fold_0冻结开发权重，accepted=false，不代表准确率或最终选择。权重与归一化核对冻结清单，模型结构核对manifest_start原SHA。没有专家位置补峰，无分类性能评分。假后端不对外伪装CLASS_RESULT。

原始ECG-UART-1被现有Monitor记录，17字节分块回放后raw.log、samples.csv、events.csv、status.csv、sessions.jsonl、summary.json和waveform.svg共7份逐字节一致，解析错误/源波形缺口/事件缺口为0。队列满、超时、迟到结果、后端错误、取消和新会话拒绝旧请求另有故障测试。这些是假传输/电脑软件证据，不能冒称真实蓝牙或Zynq运行。

## 证据与边界

派生证据：tmp/classification_20261023/record100/summary.json、requests.jsonl、results.jsonl、replay_check.json，tests_interface.log、tests_ps.log、tests_torch.log及regression.json。受保护文件76项起始哈希保存在protected.json，收尾重新核对；正式源码/检查/依赖哈希另存收尾清单。

仍未完成：原生500Hz真实输入、Scipy窗口预处理的裸机数值实现、冻结新QRS的PS/PL实现、最终合格模型/INT8/FPGA核心推理、真实无线/双USB/界面/持续运行。失败500Hz候选不采用不发布。已有目标不删改，latest镜像不替换。

## 实板阶段

用户后续确认先完成定时任务再验证；实板结果在执行后追加，不提前声称通过。

## 2026-10-24临时JTAG实板结果

用户确认先完成定时任务再上板；离线检查和文档完成后，读取JTAG实际目标，唯一Digilent JTAG-HS1序列210512180081、xc7z020/ARM Cortex-A9 #0；USB实例VID_1A86&PID_7523\6&1ef5fd6f&0&2，当前COM23。没有按旧COM号盲选，没有JDY18或人体采集参与。

在独立Vitis工作区用既有smoke匹配XSA/bit/ps7_init构建ecg_classification_smoke，源码与构建副本逐SHA相同。首次ARM编译误用XUartPs_IsTransmitEmpty实例宏却传基址而失败；读取BSP头文件，改为XUartPs_IsTransmitFifoEmpty并使等待有界，第二工作区完整构建通过。首次失败build.log/工程保留。

先开115200/8N1无流控串口，再在唯一目标临时rst/configure/init/dow/con；不改PS7配置/MIO/供电、不写Flash。构建ID71ff975364004145，串口完整返回7项PASS及PASS ECG_CLASS_INTERFACE failures=0。检查为RR_FLOAT32_CLIP、BOUNDED_QUEUE_BUSY、IDENTITY_COMPLETE、TIMEOUT_LATE_REJECT、FIRST_RR_UNKNOWN、RESET_STALE_REJECT、INVALID_DUPLICATE_SINGLE_FLIGHT。测试时间参数为受控输入，未测实际系统定时器、推理耗时或采样节拍。

正式原字节证据：[UART](classification_board_20261024/uart.log)、[JTAG](classification_board_20261024/jtag.log)。UART345字节，SHA256=dbe3364a79c0be7d9ff13a113c72fc090b167cc7ca97593b7eb7679db972c2e8。新ELF与匹配组合清单如下；全构建/身份/验证摘要在tmp/classification_20261023/vitis_workspace_02/build_manifest.json及board_01/plan.json/result.json。串口句柄已关闭。

范围仅ARM已准备张量/队列管理，不含QRS、CNN或AXI数据计算，也不是ECG-IN-1实时输入输出、真实无线/双USB界面或连续运行通过。新ELF留tmp候选，不自动写入latest；旧发布17产物保持原字节。

| 产物 | 字节数 | SHA256 |
| --- | ---: | --- |
| releases/latest/smoke/hardware/ecg_system_candidate.bit | 4045773 | d6471189437faa4dd3ffb402c4a8cff2f3b39a5349ba836a7a61f33273f50cfb |
| releases/latest/smoke/hardware/ecg_system_candidate.xsa | 321430 | fea241041311c9b40b0db9806c66a6ada2175b84c84ff571f72de2efd7bc6248 |
| releases/latest/smoke/hardware/ps7_init.tcl | 27602 | 02fa20dccd77fc2e5517a57d810289b2003afd3b82884a96723a7f9e968657f9 |
| tmp/classification_20261023/vitis_workspace_02/ecg_classification_smoke/build/ecg_classification_smoke.elf | 284428 | 0e7a03f20c85cf04f363d0bdc6b90eb566c62d5dfb331a54cdfacac399409253 |

收尾补记：按更新清单294文件复制到独立临时检出目录，完整性/124份Python解析/29模型基线核验通过；不带作者历史tmp时13项接口测试通过。76份保护文件与起始SHA全部相同，冻结QRS29源和latest17产物检查通过。新文档相对链接核验通过。单次automation-2已从应用删除，不会变成每日任务；断点摘要tmp/classification_20261023/final_checkpoint.json。未提交、推送或替换发布。
