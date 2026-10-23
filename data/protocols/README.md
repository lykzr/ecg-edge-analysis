# 协议文件位置说明

本目录不再存放协议，仅保留迁移说明。

2026-10-23 结构：

- QRS 协议在 `data/` 根目录：
  - `data/qrs_research_protocol.json`
  - `data/qrs_v4_protocol.json`
  - `data/qrs_v5_protocol.json`
  - `data/qrs_noise_protocol.json`
- CNN/模型协议在 `model/protocols/`：
  - `model/protocols/cnn_*_protocol.json`（8 个）

历史：2026-10-22 曾把协议集中到本目录，但没有同步脚本/清单默认路径；2026-10-23 按 AGENTS.md 第 6 节修复引用后恢复原布局，随后又把 CNN 协议从 `data/` 迁入 `model/protocols/`。旧协议字节保持不变，历史内部路径字样不改写。
