# Docs Records 最终整理 - 2026-10-22

整理日期：2026-10-22

## 整理目标

将 `docs/records/` 中的临时记录文件移到 `tmp/`，只保留最核心的文档。

## 整理结果

### 移到 tmp/docs_dated_records_20261022/ 的文件（32个）
所有带日期后缀的临时记录文件，包括：
- CNN 模型实验记录（8个）
- QRS 算法改进记录（7个）
- 系统集成和发布记录（9个）
- 板上验证和桥接记录（5个）
- 文档维护记录（3个）

### 保留在 docs/records/ 的核心文档（6个）

**关键实验记录：**
1. `lykzr.md` (220KB) - **完整的实验修改日志**（最重要）
2. `bringup_history.md` (15KB) - 系统启动历史
3. `offline_qrs_evaluation.md` (6KB) - QRS 离线评估结果
4. `readme_history.md` (20KB) - README 演进历史

**验证记录：**
5. `hello_world_validation.md` (1.3KB) - Hello World 验证
6. `smoke_board_validation_20261017.md` (2.7KB) - Smoke 板上验证

**子目录：**
- `smoke_board_20261017/` - Smoke 测试详细数据

## 清理原则

### 保留的文档特征
- 长期参考价值的实验总结
- 关键验证结果
- 历史演进记录
- 不带具体日期后缀的文档名

### 移到 tmp/ 的文档特征
- 带日期后缀的临时记录
- 特定时间点的状态快照
- 一次性的集成/发布记录
- 中间过程记录

## 目录对比

**整理前：** docs/records/ 约 40 个文件
**整理后：** docs/records/ 只有 6 个核心文档 + 1 个子目录
**移除：** 32 个临时记录 + 101 个日志文件

## 备份位置

- 临时记录：`tmp/docs_dated_records_20261022/`
- 日志文件：`tmp/docs_logs_20261022/`

## 核心文档说明

### lykzr.md - 主实验日志
这是项目最重要的记录，包含所有关键设计决策、实验过程、失败分析和修正。应该持续更新。

### 其他核心文档
- `bringup_history.md` - 记录系统从零到运行的过程
- `offline_qrs_evaluation.md` - QRS 算法的标准评估结果
- `readme_history.md` - 项目文档的演进过程
- `hello_world_validation.md` - 最基础的验证
- `smoke_board_validation_20261017.md` - 关键的板上验证（保留日期因为是重要里程碑）

## 未来维护建议

1. **只在 docs/records/ 保留核心文档**
2. **临时记录都放 tmp/**
3. **重要实验结果追加到 lykzr.md**
4. **定期清理 tmp/ 中不再需要的记录**

## 验证

```powershell
# 核心文档列表
ls C:\Users\23006\Desktop\ecg_edge\docs\records\*.md

# 临时记录备份
ls C:\Users\23006\Desktop\ecg_edge\tmp\docs_dated_records_20261022\
ls C:\Users\23006\Desktop\ecg_edge\tmp\docs_logs_20261022\
```

---

**文件结构规范全部完成，项目目录现在清晰简洁。**

## 2026-10-23 恢复被引用记录

结构整理后，`sim/checkout_files.json`、`releases/latest/manifest.json` 与 `artifacts.json` 仍引用部分带日期记录。2026-10-23 已从 `tmp/research_handoff_20261022/portable_final/docs/records/` 恢复下列 12 个文件（哈希一致）：

`ads1292_20261019.md`、`bridge_board_20261020.md`、`evaluation_handoff_20261022.md`、`qrs_auto_20261021.md`、`qrs_continue_20261021.md`、`qrs_peak_20261021.md`、`stream_500_20261019.md`、`stream_board_20261020.md`、`usb_bridge_20261019.md`、`uart_bridge_csv_20261020_pass.log`、`uart_bridge_synth_20261020_pass.log`、`uart_stream_20261020_pass.log`；并恢复 `smoke_board_20261017/jtag_smoke_pass.log`、`uart_smoke_pass.log`。

其余带日期记录仍按 2026-10-22 的整理保存在 `tmp/docs_dated_records_20261022/` 与 `tmp/docs_logs_20261022/`，未批量回填。
