# 性能测量入口

## 分开统计的时间

| 字段/阶段 | 起止及含义 | 不可作何解释 |
| --- | --- | --- |
| init_roundtrip | PC构造I到读到READY | 含部分写/传输/板端初始化及读调度，不是纯计算 |
| batch_roundtrip | 构造D到完整W及ACCEPTED | 含链路、板端工作及PC接收，不是CNN时间 |
| finish_roundtrip | 构造F到END/DONE | 含收尾通信，不是切拍时间 |
| session_wall | 客户机建立到DONE | 含源节拍/队列/通信，不能宣称处理核心速度 |
| qrs_cpu_s | C主机从首样本push到最后push的CPU时间 | 不包含采样等待、不是ARM时间 |
| pipeline_including_qrs_cpu_s | 另一个C回放的完整QRS/切拍/预处理CPU时间 | 与qrs_cpu_s重叠，不能相加或相减得精确分阶段耗时 |
| QRS确认/窗口ready逻辑等待 | emitted或ready_at减源position，单位为样本 | 是算法所需上下文，不是CPU执行时间；不机械与其他重叠等待相加 |

PC通信摘要新增timing字典，各阶段只有count/total/min/max/mean，固定阶段数，不存无限逐批列表。未完成批次不进入成功往返统计，摘要reason/error仍决定会话是否成功。

## 主机回放

已有GCC和Python标准库即可运行，无模型/原始数据库依赖：

```powershell
python -B sim/check_host_performance.py --output tmp/performance_new
```

受控36000点脉冲三次分别记录C两条重叠路径、事件数量、逻辑等待、编译器及源码SHA。Windows clock()分辨率记录于摘要，短时结果只能作计时入口检查，不当精准基准。推理及PL字段明确为null。

## 最终ARM/FPGA比较条件

须相同模型、输入、预处理、精度与有效心拍；分别报告传输、排队、核执行、完整确认延迟和端到端显示。当前没有最终模型/PL核心，因此不填速度倍数。ARM计时需实际全局定时器边界，PL需匹配时钟/周期/AXI完成同步；计时协议不更改现有串口E语义。实机吞吐、资源与时序、峰值队列和同负载功耗后续独立验收。
