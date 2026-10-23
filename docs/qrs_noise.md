# QRS官方噪声压力评估

本入口固定使用研究26，不训练或调参数。输入是PhysioNet NSTDB 1.0.0中118/119的12个电极移动加噪版本及MIT-BIH的两个干净参考；属于已知患者开发压力测试，不是独立测试、实时实现或板上验收。

## 输入和环境

使用已有QRS环境，依赖见data/requirements_qrs.txt。原始数据、两个数据库各自的官方SHA256SUMS及下载凭据放tmp；不打包交接、默认不纳入Git。正式脚本不自动下载或安装。

输入目录应包含42个hea/dat/atr文件、NST官方SHA256SUMS.txt、MIT官方MITDB_SHA256SUMS.txt及verified_checksums.json。后者只是派生索引，每项仍须匹配对应官方清单；解码器支持官方212和16两种编码，检查首值、校验和、样本数、标注EOF和边界，并与WFDB完整数字解码对照。原文件保持不变。

## 两种输入映射

data/qrs_noise_protocol.json固定数据、计分和源码哈希。NST与MIT原始数据的ADC零点表示有差异，因此分别运行两臂，不能拼接各自最佳成绩：

- header：沿用正式共享读取器，根据头文件gain(baseline)解码。
- adc_zero：独立输入表示诊断臂，以头文件ADC zero字段作为映射零点；要求未添加噪声的前5分钟逐点对应干净参考。不拟合偏移、不借心拍标注对齐；此臂不能直接视为实际设备幅值合同。

全段包含启动、尾部和低质量区间。匹配只执行一次，再按参考位置归属时间块；误检按检出位置归属。首5分钟无添加噪声，随后2分钟加噪/2分钟不加噪交替。无添加噪声不等于无原生伪迹。RR分块只统计同块内相邻且一一匹配的参考/检出间期，完整RR指标仍计全段。

## 标注版本

当前官方NST的119参考与当前MIT119有35个V拍位置不同，最大差31样本；总数/类型顺序一致。主压力表统一用同一基础记录的NST官方标注，连干净参考也按该标注计分；每项另在mit_annotation_score中保存MIT当前标注计分作为副表。118两库标注相同。不改原始文件，不按结果挑标注或拟合时间偏移。原42条MIT回归仍使用原冻结协议，不能与这张压力表拼接。

## 运行

从工程根目录执行，替换实际Python和输入路径。输出必须是tmp下不存在的新目录。

```powershell
python -B -m unittest discover -s sim -p test_qrs_noise.py -v
python -B data/download_qrs_noise.py --raw-dir tmp/noise_raw --verify-only
python -B data/evaluate_qrs_noise.py --raw-dir tmp/noise_test_20261023/raw --output-dir tmp/noise_test_20261023/preflight_header --records 118 118e24 --mapping header
python -B data/evaluate_qrs_noise.py --raw-dir tmp/noise_test_20261023/raw --output-dir tmp/noise_test_20261023/full_header --mapping header
python -B data/evaluate_qrs_noise.py --raw-dir tmp/noise_test_20261023/raw --output-dir tmp/noise_test_20261023/full_adc_zero --mapping adc_zero
```

两臂都应先通过配对预检。每条记录保存位置、事件、匹配、FN、FP及summary.json；每完成一条更新总摘要，进程中断时已有结果不会被覆盖。源码/数据发生变化停止受影响实验，不改冻结清单凑数。

第一次获取数据时，明确执行data/download_qrs_noise.py并省略--verify-only；它仅下载预定两库的42文件及官方校验，不安装软件。已有文件不覆盖，SHA不符停止。之后--verify-only只读核验，不联网、不改索引。所有命令的--raw-dir应使用同一个实际目录；示例noise_raw是可替换名称。

本压力实验用于定位误检和漏检随噪声变化的原因，不承诺极低SNR满足99%。原42条门槛不变。实际结果与失败见[实验记录](records/qrs_noise_20261023.md)。

这里的V召回是“专家标注为V的心搏有多少被QRS检出”，不是CNN对V类的分类召回。官方em噪声来自实际噪声记录，但本实验是混入公开ECG的离线压力测试，不是ADS1292R实采或上板测试。SNR标签只对应加噪区间，全记录成绩同时包含未加噪区间，需连同time_blocks阅读。
