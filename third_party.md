# 第三方来源与许可边界

根 LICENSE 的 MIT 许可用于本项目贡献者有权授权的自有代码和文档，不替代第三方原有许可。后续引入新组件时保留其版权和许可，并在本文件追加来源。

| 内容 | 来源与处理 |
| --- | --- |
| MIT-BIH 100号波形和标注 | [PhysioNet MIT-BIH 1.0.0](https://physionet.org/content/mitdb/1.0.0/)，本库提供获取脚本与引用；原始文件留在 tmp/，不作为自有代码改标MIT。数据使用条件以该版本官方页面及原许可为准。 |
| AMD BSP、FSBL、IP及工具生成内容 | 使用Vivado/Vitis 2026.1生成，相关代码/库保留AMD及其依赖的原许可。releases/latest中的二进制不意味着其中所有组成部分重新授权为MIT；正式对外发布前补查对应源码/许可交付要求。 |
| 正点原子原理图、手册与官方工程 | 原始资料只读参考，未作为本项目自有源码重新授权。不要将下载盘或手册自动上传到仓库。 |
| 竞赛指南及参考PDF | docs/reference/为本地参考，忽略共享；未确认公开再分发权限。 |
| Python、matplotlib、Vivado/Vitis | 外部运行/构建工具，按各自许可独立使用，本库不复制其安装目录。 |

数据库引用：Moody G, Mark R. MIT-BIH Arrhythmia Database, version 1.0.0. PhysioNet. DOI:10.13026/C2F305。原论文：Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Engineering in Medicine and Biology 20(3):45–50, 2001。

自有实现未因参考资料而取得第三方资产的版权。当前仍是开发仓库，完整第三方组件和最终发布包许可审查列入计划，尚未声称已全部完成。
