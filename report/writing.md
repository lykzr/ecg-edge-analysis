# 报告与海报编写说明

## 当前文件

| 文件 | 用途 |
| --- | --- |
| [report.pdf](report.pdf) | 当前9页技术报告，由正式TeX直接编译 |
| [poster.pptx](poster.pptx) | 中、英文各1页海报，图片及图表数据已嵌入 |
| [poster.pdf](poster.pdf) | PowerPoint内置导出的两页海报PDF |
| [report.tex](report.tex) | 报告唯一内容和排版主源 |
| [tools/build_report.ps1](tools/build_report.ps1) | 两遍XeLaTeX编译入口 |
| [competition_brief.md](competition_brief.md) | 当前硬件加速数据及写作依据 |
| [report.md](report.md)、[handoff.md](handoff.md) | 工程实现说明和接手说明 |

## 编辑及编译

先修改 `report.tex`，再在项目根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File report/tools/build_report.ps1
```

使用已有TeX Live、宋体、Times New Roman及TeX Gyre Termes Math字体。脚本按自身位置定位，编译结果和日志写入新建的 `tmp/report_tex_build_<时间>/`，不自动覆盖正式PDF。核对文字、字体、公式、表格和分页后，将旧稿原样归档至 `tmp/report/last/`，再替换正式PDF；覆盖前关闭PDF阅读器，并确认没有他人并发修改。

框图、模板页眉及报告实际使用的两张照片在 `source/figures/`，随源码保存。`attachments/` 整体忽略，仅保留本机素材；海报图片已内嵌。第3页使用用户提供的Vivado截图，仅裁去界面边栏和控制台，保留原模块与连线；对应 `build/build_cnn_int8_fast_pl.tcl` 的三核连接，替换原概括分工示意图。横向照片及13项标注直接由TeX绘制，不在PDF上后期叠加。PPT可直接编辑，不依赖本机临时目录。当前没有与PDF同步的Word稿，历史Word稿不能作为当前源使用。

## 内容与口径

报告第7页3.4节列出优化前后四行对照；表后说明浮点调用耗时降低28.49%、INT8降低37.61%。优化INT8含板内AXI读写的同精度加速为9.015倍，优化浮点为4.174倍；两者不表示整条采集与显示链路加速。当前报告已删除补充测量空表。第8页3.5节按原三核、浮点优化后和INT8优化后三阶段比较资源；4.1节按识别效果、INT8量化、片上存储、输出时序约束和长期运行等方向说明扩展。第9页4.2节说明五项工程技能及25项行为测试，保留原始交互摘录，并明确事后提炼的提示词模板不能代替原始对话或板测。当前9页，按既定口径含180字预留合计5953字，未超6000字上限。技能依据为 `skill/validation.json`。九条参考文献已逐项对照原始来源，评估偏差文献用于4.1节；QRS正文按滤波、心跳检测和切拍顺序说明。

海报使用12个有效拍的网页示例，固定性能基准为60秒合成输入的72个有效拍，两者分别标明。分类质量与速度分开报告；静态资源不作为实时忙碌率。数值来源见 `competition_brief.md` 及 `docs/evidence/cnn_int8_fast_20261103/summary.json`、`docs/evidence/cnn_fast_20261103/summary.json`。

## 历史资料位置

旧Word/TeX、旧配图和PDF叠图脚本，以及原来附件中的手册、模板、源码快照、旧编写说明与检查收据，已原字节归档至本地 `tmp/report/last/report_cleanup_20261104_01/`。其中 `paths.json` 保存每个原路径、归档路径、长度与SHA256；`before_edit/` 保留整理前的编写说明和忽略规则。历史记录中的路径和结论保留原文，不能用旧脚本覆盖当前源。

其他历次报告、海报修改记录与备份仍保留在 `tmp/report/`、`tmp/report/last/` 和 `docs/records/lykzr.md`，不作为当前构建依赖。
