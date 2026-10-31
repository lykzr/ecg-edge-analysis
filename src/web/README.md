# 网页客户端

本目录保存网页界面、账户/记录业务与本项目实时后台的适配。页面采用来源项目的布局；设备协议、采集和中转复用 `src/pc`，原Tk入口继续保留。

| 位置 | 职责 |
| --- | --- |
| frontend | React/TypeScript页面、波形与请求适配 |
| business_logic | FastAPI、SQLite账户/记录/授权/任务与实时API |
| ai_model | 来源项目的可选离线分类/解释适配，默认无模型 |
| signal_processing/python | 离线CSV和显示滤波，不替代板端实时处理 |
| hardware | 合成记录及ADS导出辅助，不采用上游固件协议 |
| run.py | 本机、单进程、同源网页启动入口 |

从项目根运行 `./build/build_web.ps1` 构建，再用独立环境执行 `python -B src/web/run.py`。环境建立、操作、数据目录与验收边界见[网页教程](../../docs/web_monitor.md)；软件测试在 `sim/web`。[来源与许可](NOTICE.md)、[导入原始哈希](upstream.json)用于追溯；导入哈希是改动前的来源身份，不表示当前适配文件未修改。
