# 评估计划、文件整理与隔离交接记录

## 本轮范围与决定

用户要求把检索结论写计划、安排凌晨3点接续，并让DS先在隔离位置准备；同时整理无用文件并保证交接可用。共用计划保持总计划加采集/主体/模型三类结构，检索依据与10月23—25日的顺序、停止条件合入总计划末尾；system2.15和model3.7分别落到职责。不新增第四份正式计划，初稿可恢复放tmp/backup/method_plan_20261022。

模型训练仍暂停；Class-Balanced只列后续获授权的小对照，不开独立6人，不把原42条或118/119加噪衍生称新独立测试。先受控噪声定位，最多一个主改动，达标后才谈同源实现/上板；三天给明确结果，不承诺全部达标。研究/官方来源链接直接放总计划。

## 交接缺口与修正

原最好研究26的代码和源事件CSV仅在本机tmp，别人拿正式文件无法复现。本轮将必要4份研究源保留在src/reference/qrs_research，记录原SHA与新SHA及仅相对导入/来源注释改动；独立replay.py从原码重新生成两路源事件并做相同200ms截止定位。入口data/benchmark_qrs_research.py和新协议不依赖旧tmp事件文件，明确未合格、已知开发回归、离线重放。历史v5及既往记录原字节不改；新协议去掉过期untouched里程碑，不追改旧哈希。原型仍保留无界audit诊断列表，整个离线入口保存全记录/事件，未宣称完整在线内存有界或PS/RTL/500Hz支持。来源/许可由provenance.json、third_party和原MIT文本保留，未复制GPL Hamilton实现。

重新从原码跑完整42条、650000点/条后，与26的210份CSV（事件/位置/匹配/漏检/误检）逐字节一致；TP/FN/FP、全部门槛、类型/时间块和确认延迟也一致。新快照仍18/19加23/23，105仍未达标，不是新算法提高或新的独立验证。摘要tmp/research_handoff_20261022/accuracy_move_check.json，完整输出development/evaluation；不更新release。

## DS小任务与可恢复隔离

正式说明docs/ds_task.md和生成器sim/prepare_ds_workspace.py可随工程交接。当前隔离目录tmp/ds_noise_20261022，包含input/project只读源副本及118/119原始输入、input_manifest.json、check_inputs.py、TASK.md和本轮专用AGENTS；38份输入SHA检查通过。仅允许DS写work/output/logs，不读取原工程、不Git/安装/下载/训练/板卡。让其只做来源清单、NST协议草案和合成自检，最后写output/DONE.json；不是让其改检测器。报告放output/report.md，README只写工程说明。DS尚未执行，本轮不冒称其工作完成。

不依赖本机旧副本，另一机器在项目根用已有Python执行：

```powershell
python -B sim/prepare_ds_workspace.py --output-dir tmp/ds_noise_local
python -B tmp/ds_noise_local/check_inputs.py
```

如已取得并校验118/119，可增加--raw-dir <mit_raw_dir>；不带原始数据也能准备标准库小任务，缺项如实报告。生成器拒绝覆盖现存目录；环境和数据需要接收方按授权准备，未自动安装或上传。工具权限若可配，只给DS隔离目录；SHA检查能发现变更，不等于操作系统强制隔离。独立负例副本能检测输入篡改，实际DS目录未被该测试修改。交付前说明曾校正为report.md及合并总计划，空的旧生成副本已可恢复归档ds_workspace_draft，用户使用的是最新tmp/ds_noise_20261022。

## 文件整理与忽略范围

根目录8份旧Vivado backup日志/日志脚本经正式目录无引用检查、绝对路径与目标无覆盖检查、逐文件SHA比对后移入tmp/history/root_vivado_logs_20261022，manifest.json保留原位置、大小和SHA。不搬当前vivado.log/jou、.Xil或可能活动工具工程。其余源码、复现入口、旧协议/权重/验收记录仍是依赖或可追溯证据，保留。新增/tmp隔离副本、完整评估和日志由现有.gitignore覆盖，备份日志原先也已被*.log/*.jou忽略，无需为产生改动机械改ignore。

## 便携与检查边界

sim/checkout_files.json补齐新源码/协议/说明/生成器，不把生成的tmp作为交接前提。复制required清单到新的英文目录portable_checkout后，静态交接检查与训练交接隔离检查通过，不要求原tmp或测试患者数据。另在该新路径独立导入新包，完整重放100/117/203/210四条各650000点，与本轮原路径事件完全一致，portable_runtime.log保留。这是同一电脑换目录运行，不是第二台电脑或Vivado/Vitis/硬件的实测。

最终说明更新后再次生成干净目录并复核清单、链接、源哈希和受保护文件。根README、materials_review、模型基线/保留协议、旧QRS冻结协议、当前release均不更换；没有检查或修改Git暂存区，文件验证不等于已提交或已推送。

## 定时与接续

专用接口已创建并更新qrs，ACTIVE，下一次北京时间2026年10月23日03:00、COUNT=1、当前对话。先审核DS的DONE和输入SHA，再核官方NST数据与计分，完成有边界的一轮；无DS产物可接着准备，不等待或重跑同一正在执行任务。任务结束删除，不改为重复。本轮只准备交接与方法计划，没有恢复训练或操作板卡。


准备阶段补查发现读取器还需要官方SHA256SUMS.txt，仅六个原始文件不足以直接调用load_record。生成器已补齐并验证每个原始SHA；最终DS输入为39份，两条650000点在隔离副本用实际读取器完成官方SHA、头信息、校验和和完整解码，ds_data_check.json通过。初始38份的文件清单校验通过不代表依赖已完整，本次补件记录保留。交付前控制文件与全部输入的独立凭据在tmp/research_handoff_20261022/ds_receipt.json；03:00先核该凭据，防止只信DS自己的PASS或被改过的清单。


## 2026-10-23：DSH审核与定时取消

用户要求停止定时并审查DSH结果，随后要求同步计划。专用automation接口删除qrs返回deleted；不启动03:00任务，不重跑QRS，不恢复模型训练。此前本轮目录/发布整理仅做读取，尚无写入；被本次任务暂停，不能报成已完成。

读取隔离目录TASK/AGENTS、report.md、inventory/protocol两份JSON、build_deliverables.py、noise_eval.py、selfcheck/readiness输出及日志。依据交接前tmp/research_handoff_20261022/ds_receipt.json独立核验：39输入、4控制文件SHA一致，输入文件集合无新增；inventory39项大小/哈希一致。此范围不证明正式工程的其他文件从未被改过。

DSH记录合成自检12/12通过，未运行真实波形或检测器，缺12份NST共36个文件与相应校验。输出report.md声称结束校验已做且DONE已写，但实际logs/check_inputs_after.log、output/DONE.json均不存在：本次不能按完成验收。当前审查时未发现后续生成文件，不补写或冒签。

独立只读导入两个匹配函数，用random.Random(20261023)生成1000组严格递增小数组、固定54样本容差，对照正式data/ecg_dataset.py，0差异；该正式文件与隔离快照SHA一致。未执行DSH run_selfcheck/main或生成器，不覆盖其证据。报告的12/12只核读，非本轮重跑。

发现待修：1）自检对固定work/_exists使用mkdir(exist_ok=True)再rmdir，若原有空目录会删除它；不安全，不能直接运行。2）--fs/--tolerance-samples在selfcheck路径被硬编码360/54忽略，且负容差未拒绝；只读探针match_beats([100],[100],-1)直接给FN/FP。3）validate_series把[1.9,2.9]静默转为[1,2]；需明确严格整数。4）所谓截断输入只截断检测位置列表，不检查原始波形长度；计分也未实现V召回。5）readiness只检查存在性，generator缺失项硬编码，不能当真实数据完整性/官方校验通过。6）DSH承认首次失败日志被成功日志覆盖，失败证据不完整，保留此事实。

结论：准备成果部分有用，尚未完成交付、尚不能作为正式噪声入口；没有抗噪改善或合格证据。同步总计划与system的实际勾选/待办，保留旧记录，不改DSH原件、算法、release、根README、materials_review、模型基线；无Git、安装、板卡或文件删除。备份tmp/backup/dsh_review_20261023_01。
