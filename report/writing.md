# 报告与海报材料说明

## 当前文件

| 文件 | 用途 |
| --- | --- |
| [report.pdf](report.pdf) | 当前9页技术报告，包含横向实物照片和矢量标注 |
| [poster_bilingual.pptx](poster_bilingual.pptx) | 当前中、英文各1页海报，采用竞赛模板，可继续编辑 |
| [source/report_layout.docx](source/report_layout.docx) | 当前PDF的文字排版源，实物照片位置为占位；导出后需叠加照片及标注 |
| [source/legacy/report.tex](source/legacy/report.tex)、[source/legacy/report.docx](source/legacy/report.docx) | 较早版本的TeX和Word源，原样保留，不与当前PDF混称同版 |
| [competition_brief.md](competition_brief.md) | 新提交的比赛素材与实测数据，供后续内容修订核对 |
| [report.md](report.md)、[handoff.md](handoff.md) | 工程实现说明与接手说明，不是排版报告 |

本次只迁移位置和修复材料路径，没有改动PDF、PPT及Word、TeX的正文。新提交的性能数据尚未写入现有PDF/PPT；修订时应以对应实测证据为依据，不能将旧稿数字当成最新结果。

## 编辑及导出

修改当前报告文字时使用 `source/report_layout.docx`，保留两处实物照片题注和定高占位。将它通过Word导出为临时PDF，例如 `tmp/report_build/base.pdf`，再从项目根执行：

```powershell
python -B report/tools/compose_pdf.py --base tmp/report_build/base.pdf --output tmp/report_build/report.pdf
```

该工具使用Python的 `pypdf`、`pdfplumber`、`reportlab` 和Windows宋体；照片从 `report/attachments/figures/` 读取，13项标注来自 `report/tools/photo_labels.json`。工具拒绝照片区域存在正文或照片放置越出底部的布局，输出配套位置记录；修改文字后仍需逐页检查排版。确认后再替换正式PDF，旧版先归档至本地 `tmp/report/last/`。

PPT的图片均已嵌入，可直接编辑，不依赖原作者的临时目录。原始采集端、开发板及整机照片放在 `attachments/figures/`，图中文字标注不修改原始照片像素。较早TeX使用的 `figures/` 与TeX一起保留在 `source/legacy/`，从该目录编译即可解析配图。

## 本地参考与历史

原 `tmp/report/attcachment/` 已移至 `report/attachments/`。其中商家手册、模板、原始要求、旧工程摘录、旧编写说明及检查收据保留本地并忽略，不自动上传；正式实物照片和校徽按精确白名单随Git保存。附件中的历史绝对路径和哈希收据原样保留，不回写成新的来源记录。

原有历史稿、失败稿、渲染预览和一次性修改脚本仍在 `tmp/report/`。本次逐文件迁移映射及哈希检查保存在本地 `tmp/report/migration_20261103/paths.json`。它们不属于运行依赖，不能用旧生成脚本覆盖当前正式稿。
