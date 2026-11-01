# 心拍模型与可选节律模型适配

默认ECG_MODEL_TYPE=hgb，调用仓库model/inference的完整逐心拍研究模型，固定v92/fold0。输入为连续500Hz单导联mV，未额外滤波输入使用hp05，匹配因果高通后的标准输入须显式选raw。分类在独立电脑进程执行，不是Zynq上的ARM/FPGA分类；不是正式质量合格模型。

ECG_MODEL_TYPE=none显式关闭；ECG_HGB_PYTHON可指定独立模型Python，未指定时使用网页当前Python。环境变量优先于src/web/.env；修改后重启。HGB解释固定用逐拍模板，不把N解释为健康，不把VF解释为心室颤动，不发送外部解释请求。运行和依赖见[接入说明](../../../docs/model_integration.md)。

OpenECG适配代码保留为未启用候选：严格500Hz、至少10秒，仅用前10秒；未安装依赖或权重，也未验收模型效果。未知输出标签不自动归为异常。其记录级输出不能静默替换N/S/V/F心拍协议。

本项目分类接入缺项见[当前实现与缺项](../../../report/report.md)，当前目标仍包括CNN、INT8和FPGA推理。来源许可见[NOTICE](../NOTICE.md)。
