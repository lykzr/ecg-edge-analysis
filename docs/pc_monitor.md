# PC离线波形监视器

当前实现用Python标准库和Tkinter提供演示、ECG-UART-1日志回放、波形/事件显示、缺口统计及文件记录。不需要板卡、模型、PySerial或新装绘图库；本版本没有真实串口接收、板端命令发送或PS流式程序。

## 启动界面

在项目根目录运行，选择带Tkinter的Python3.10或以上版本。当前本机已验证的解释器为：

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B src/pc/ecg_monitor.py
```

界面操作：

1. 点**开始演示**，查看60秒数学合成波形及指定位置标记；这没有运行QRS或CNN，不是设备实测。
2. 点**停止并保存**，保留原始字节、样本/事件CSV及摘要。再次开始会建立新目录，不覆盖旧记录。
3. 点**打开日志回放**，选择本程序保存的raw.log或同版协议的板到PC行日志。回放按序快速处理，不模拟真实采样墙钟速度。
4. 点**导出当前SVG**保存当前显示范围的矢量图。SVG只是补充，不能替代原始记录；此版没有PNG导出或CSV导入。

默认输出在tmp/pc_monitor_logs下的独立会话目录。顶部明确显示演示/文件来源；界面上的SYNTH/REPLAY/ADC是元数据声明，不是本机认证的实物来源。没有滤波/模型时不造滤波曲线或N类标签；未知电压比例显示“码值（未标定）”，未知采样率不生成秒轴。

旧smoke日志只有BEGIN/PASS/FAIL等自检文本，不含H/W波形帧，打开它不会凭空显示ECG。无波形时程序保留原日志并提示，不应把它理解为smoke未通过。

## 无界面复现

输出目录必须尚不存在，替换新的英文目录名：

```powershell
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B src/pc/ecg_monitor.py --headless --demo --seconds 10.01 --output-dir tmp/pc_demo_new
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B src/pc/ecg_monitor.py --headless --replay tmp/pc_demo_new/raw.log --output-dir tmp/pc_replay_new
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B src/pc/ecg_monitor.py --ui-self-test --output-dir tmp/pc_ui_check_new
& './tmp/qrs_benchmark_env/Scripts/python.exe' -B -m unittest discover -s sim -p test_pc_monitor.py
```

演示参数--fs/--scale只控制数学源，默认360Hz、scale=-1（未标定）。要检查声明单位换算，可显式设置--scale 4096；这不代表真实ADC已经校准。演示事件由SYNTH-MARKERS指定，不是当前PL算法输出，也不能用于检测准确率报告。

--ui-self-test创建隐藏窗口，检查Canvas波形/事件图元和未知值显示后退出，不连接串口；它不等于人工交互或实物联调验收。

## 记录、限额和失败

| 文件 | 内容 |
| --- | --- |
| raw.log | 逐字节保存传入数据，包括坏行/未知行，不做换行或编码改写 |
| sessions.jsonl | 合法会话元数据；同会话相同H重发不另开会话 |
| samples.csv | 会话/来源/检测器、fs/scale、uint32序号及展开位置、名义时间、raw/filt及可用mV换算 |
| events.csv | 原始事件号、候选位置、RR、心率、类别/分数；没有可确认时间映射时不猜事件时间 |
| status.csv | 状态字段；FIFO事件丢弃、源采样丢弃和发送丢弃分别保存 |
| summary.json | 结束原因、累计解析/样本/事件/缺口计数、最后元数据及关闭错误 |
| waveform.svg | 无界面成功处理后的当前显示缓存图；GUI通过按钮导出 |

未知数值在CSV中留空，类别未知保留?；原始raw=-1/0仍是正常值，不能解释为缺失。样本时间由展开后的序号/fs生成，是逻辑采样时间，不是串口到达时间。接收首批之前的缺失数量未知，不补造缺口；重复或倒序帧计错且不推进序号。图中跨缺口断线，事件只在实际接收到的相应位置上标记，允许事件先于波形到达。

显示缓存最多4096点、256事件、20条日志；完整已接收记录仍写磁盘。输入按块读取、单行最多256字节、单文件最多256个不同会话；不同session切换显示缓存，禁止新会话后重用旧ID，同ID改元数据计错。源/滤波群延迟未定时不自动对齐或拟合偏移。

原始与解码文件累计默认64MiB，--max-bytes可配置、最少1024。到达上限、文件错误或磁盘写入失败时停止并保留已有文件，summary另占少量空间；磁盘完全写满时摘要本身也可能写失败，界面/命令行会报错。本轮不自动滚动、不删除历史，最终连续采集保留策略仍可再评审。限额停止时原始日志可能已保留最后一块、但CSV只写完其前半部分，结束原因必须一起检查，不能当完整采集通过。

CLI退出码0表示程序完成有效波形处理，不意味着输入无坏行或设备验收通过；查看summary计数。限额、I/O错误或没有协议波形返回非零。达到限额后的残留原始输入可在新目录重新回放，不能覆盖原失败目录。

## 协议与范围

当前PC软件规则见[UART协议](uart_protocol.md#13-pc软件v1实现约定)，它在旧草案上补充session/source/detector、W的实际批量n、分开的丢弃计数。旧6字段H/无n的W只是此前草案，本程序不静默猜格式。无行校验基线已明确；此版不接受声明LINE_XOR的输入，不自动尝试多种校验。

后续采集端仅需适配到同版帧，真实fs、ADC位宽/增益、物理单位和滤波来源/延迟继续由实物核查。新协议板端尚未实现，不把本程序合入已通过smoke镜像，也不更新release。界面与收发实际验证结果留docs/records，本README式使用说明不放实验成绩。
