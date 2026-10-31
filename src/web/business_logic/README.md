# 网页业务后台

FastAPI提供账户、记录、趋势、备注、导出、家庭授权及持久化离线任务；SQLite迁移位于db/migrations，已有迁移文件不改写。默认数据库、上传、实时记录均位于项目tmp/web_runtime。

从项目根通过独立环境执行 `python -B src/web/run.py`，不要沿用来源工程的run_backend.py或安装路径。单进程运行；离线分析任务内存队列最多128项，溢出任务保留在数据库pending状态，空闲时补取。实时采集独立复用src/pc的有界后台，不经过离线任务队列。

实时HTTP及WebSocket接口位于app/api/live.py；用户身份、会话归属和下载边界均需核对。首条WebSocket消息提交令牌，不能把令牌放URL。网页采用HTTP有界快照轮询，WebSocket供兼容客户端使用。详见[网页教程](../../../docs/web_monitor.md)。
