# 整数算子准备

这是与最终模型无关的小规模数值/RTL工具，不加载权重，不推断分类效果，不修改现有BD、QRS或发布镜像。

## 数值合同

输入和权重均为有符号INT8、对称零点0；偏置与乘加为INT32。主机先检查`abs(bias)+CIN*KERNEL*16384 <= 2147483647`，不满足拒绝配置。算子不得依赖溢出回绕。

卷积为多输入/输出通道的一维valid、stride1、无padding无dilation。布局x[CIN][LENGTH]和w[COUT][CIN][KERNEL]；RTL展开为相同通道优先线性数组。结果按SHIFT=0..31右移，最近舍入、恰好一半远离零，最后饱和[-128,127]；可启用ReLU下限0。这里的二进制右移只是准备合同，不能替代最终模型每层乘数/尺度、残差重标度或平均池化规则。

最大池化使用有符号比较，窗口与步长同WIDTH，舍弃不足一个窗口的末尾；逐通道调用，不能跨通道池化。WIDTH须正且不大于LENGTH。

卷积start仅空闲时接受，计算期间输入/权重/偏置必须保持不变，busy时忽略start；done只脉冲一拍，reset作废本次结果，done前的y不应读取。此向量接口用于准备验证，尚不是AXI/DDR/DMA接口，后续模型结构冻结后另行设计。

## 使用

参考为[src/reference/ecg_int8_ops.py](../src/reference/ecg_int8_ops.py)，RTL为[src/rtl/ecg_int8_ops.sv](../src/rtl/ecg_int8_ops.sv)。已有Vivado环境运行：

```powershell
python -B sim/check_int8_ops.py --output tmp/int8_new --vivado-bin '<Vivado>/bin'
```

输出路径须为新tmp目录。脚本生成固定种子张量/黄金结果，编译真实RTL并以有界仿真逐值断言，不把Python模拟代替RTL。工具日志和向量留输出目录。算子仿真不等于最终CNN、INT8量化损失、综合时序或板上推理验收。

## 独立综合

已有Vivado环境，将ECG_OPS_OUTPUT设置为新的项目tmp目录后执行`vivado -mode batch -source build/check_int8_ops.tcl`。只综合默认参数的卷积算子，不加载主工程；输出利用率和DCP。综合通过不替代数值仿真，不包含实现、时序收敛、最终模型资源或板卡验收。

若受限执行上下文出现DLL重定位或引擎启动错误，不能直接认定安装损坏：先在允许本地工具执行的正常终端用同一命令复核。本轮后续标准工具及严格X比较已通过，失败和更正保留在主体记录，不需要改安装目录、编译器或权限。
