# 网页来源与许可边界

网页与离线业务源自 `wangjianlin-0/health_system-v2` 的 `ly-Integration` 分支，导入提交为 `df9fae6b46d84d91b0cb9f00b4da5fb06b0dbcde`。仓库地址保存在 `upstream.json`，原文件相对路径、导入目标与原始SHA256逐项列出。保留原作者权利，适配不改变其作者归属。

核对的该提交没有根LICENSE，不能认定这些来源文件自动适用本项目MIT。当前用户授权本地集成与审阅，不构成对外再分发许可；公开推送、打包或发布网页前，需要来源权利人明确许可。未导入原CSV样本、第三方数据、固件协议草案、STM32脚手架、OpenECG权重或二进制程序。

本项目新增实时适配层、实时页面、构建入口和测试遵循本项目自有代码许可。React、React Router、Vite、TypeScript、FastAPI、Starlette、Pydantic、Uvicorn、websockets、NumPy、SciPy、pytest和httpx等由包管理器安装，不将环境、node_modules或编译产物复制进Git。实际版本由 `requirements-lock.txt` 与 `frontend/package-lock.json` 保留，原版权及许可证随安装包保留；最终二进制分发仍需按实装组件补齐声明。

来源OpenECG适配仅为未启用的可选代码，不意味着已经获取其模型许可或完成推理。12导联ECGFounder清单为未启用参考，不作为本项目单导联权重或成果。来源的模型解释模板默认本地执行，外部解释配置不在本轮启用。
