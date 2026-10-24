# PS分类接口核心

classification.h/c管理已经准备好的float32波形128点、RR三维张量和心拍元数据。固定4个请求槽位（含正在处理的1个），通过generation隔离会话，调用方绑定模型SHA256、转换session并提供单调毫秒时钟。BUSY不接收也不推进已接收编号；完成/超时/取消只产生一次结果。重置前先取消旧请求并记录，再以非零新generation初始化。

本层不实现重采样、QRS或CNN运算，不分配AXI地址。模型SHA绑定于状态，切换模型必须重置；张量内存结构不能直接当串口线格式。状态码、输入规范和当前未知项见[分类协议](../../../docs/classification_protocol.md)。

主机核验：在已有NumPy环境运行`python -B -m unittest discover -s sim -p test_classification_ps.py -v`；需要已安装GCC，路径可由ECG_HOST_CC指定，不自动安装。正式板端应用需另行绑定实际预处理、时钟、后端和输出。
