# ECG边缘分析工程过程记录

按与[计划书](../../report/project_plan.md)一致的三类归档：信息采集、项目主体、模型训练。每类内部保持原时间顺序；跨类混合记录整条放在主要工作所属类，不拆写成多次试验。原题目/正文、失败过程、旧状态和证据路径保留；历史“smoke未上板”等是当时快照，当前smoke已按用户返回证据通过，模型仍未合格。当前任务状态以计划为准，教程与原始专题报告不合并改写。

新记录追加到相应类别末尾；涉及其他类时引用任务编号或原证据，不重复计算成果。

## 一、信息采集

当前尚无独立AFE/ADC实采成功记录。采集参数、电平/限幅、接口与采样验收见计划A01—A05；芯片候选讨论见[范围记录](ecg_scope_20261017.md)，它不等于实物联调完成。后续实际采集修改/验证追加本类。

### 2026-10-17：更正信息采集边界，纳入滤波与输出接口

用户指出原采集类别缺少滤波和输出接口。本轮在计划新增A06滤波/基线与工频抑制、A07采集输出接口和A08相关噪声验证；原B02迁到A06，不按部署位置强行把滤波留在主体。采样率/位宽/单位、原始/滤波序号及群延迟、有效/就绪、背压/丢样等交接待定义。主体保留板端与电脑的通信、PC显示/保存，二者输出接口不混用。仅修改计划/日志，没有采集、滤波实现或实测；历史混合滤波/QRS记录不拆改。

### 2026-10-19：ADS1292R资料核查与离线数据解码

板卡不在用户手中，按当前授权推进离线工作，PS流式程序仍未上板。读取新资料包的TI手册关键章节/页面、模块图、协议和STM32核心源码；确认协议34字节四点与main.c实际10字节一点不同，源码500SPS与当前合成流360Hz不同，通道用途及呼吸相位注释存在矛盾。供电、电平、人体连接与实际固件待核，不把例程注释当实物证据。

新增src/reference/ads1292.py、sim/test_ads1292.py，按已划界帧恢复24位补码/状态及两版偏移码；不自动猜帧、不丢高位、不冻结导联/单位或直接接PC。解码14项通过（含128状态组合、1000组双通道向量），PS主机8项、PC核心14项回归通过，无板卡或真实ADC参与。维护采集计划、说明/导航、测试与交接清单，并纠正PC文档“没有PS流式程序”的旧句。

详细来源、取舍、风险、命令与输出见[本轮记录](ads1292_20261019.md)和[接入说明](../ads1292.md)；备份tmp/backup/ads1292_review_20261019_01，派生阅读和检查tmp/ads1292_review_20261019。A01—A04及B10/B11不勾选；未恢复模型训练、Git或操作Flash，根README/资料索引/latest未改。

## 二、项目主体

### 2026-10-13：约束核对与下一阶段设计评审

#### 任务目标与范围

核对当前协作约束、参赛交付要求、工程实际组成与已有验证证据，确定下一步实施顺序。本轮是静态核查和设计评审，没有修改 RTL、PS7、BD、XDC 或构建脚本，没有重新运行仿真、综合、实现或下载。Git 持续暂停，没有执行 Git 命令，也未检查索引或远端状态。

当前项目根目录为 `C:/Users/23006/Desktop/ecg_edge`。根目录 `AGENTS.md` 是当前操作约束；递归文件清单只发现该文件，没有发现子目录专属 `AGENTS.md`。

#### 环境与阅读依据

- 当前可见 Vivado/Vitis 启动文件分别位于 `D:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat` 和 `D:/AMDDesignTools/2026.1/Vitis/bin/vitis.bat`。本轮仅核实文件存在，未启动工具或重新验证许可证。
- 历史验证日志声明 Vivado 2026.1；实际 XPR/BD 也记录 2026.1。
- 读取 `AGENTS.md`、`README.md`、`docs/project_plan.md`、`docs/register_map.md`、`docs/workspace_migration.md`，以及检测器、AXI 包装层、现有 testbench 和三个主要构建/测试脚本。
- 读取实际 `vivado/ecg_edge/ecg_edge.srcs/sources_1/bd/ecg_system/ecg_system.bd` 及 XPR 引用；核查 `tmp/rtl_tests/xsim.log`、`tmp/validate_navigator.log`、`tmp/rebuild.log`、`tmp/rtl_synth.log` 的完成记录。
- 本地竞赛指南 `docs/reference/amd_track_guide_2026.pdf`：完整阅读第 3.3 节相关内容，实际渲染查看 PDF 第 22–25 页（印刷第 19–22 页）。派生文本与页面放 `tmp/next_step_review/`。结论依据该本地版本，本轮没有查询后续赛事公告或报名后台。

#### 约束与交付要求

1. 板卡用户确认领航者 V2，但核心板/底板具体版本尚待实物核实。修改板级参数前须核查匹配版本的原理图、指南和官方例程，旧 AC7020 配置不能作为实物适配依据。
2. 禁止 Computer Use；正式文字中文、接口标识英文；临时和派生输出放 `tmp/`，保留原始资料和无关改动。
3. 软件参考、定点/RTL 和数据链路先行，采集前端与扩展算法后置；未核实人体连接条件，不作可直接采集人体 ECG 的结论。
4. 本地指南要求作品板上跑通，提供实测输出与参考结果比对、综合/实现报告、可复现构建、设计报告和大模型协作记录。
5. `skill/` 中须提炼已验证的可复用经验，说明适用范围、使用方式、失效条件和形成依据。普通技能包是提交要求，通用 PYNQ Skill 是单独加分项；PYNQ 是推荐实现方式，不是必须切换的技术路线。
6. 指南评分为创新/应用 30、性能/资源 20、正确性/完整性 20、大模型协作/技能包 15、文档/复现 15。工程包目录结构是推荐项；采用现有结构可行，但 README 须给推荐目录的对照。
7. 指南强烈要求开源并使用允许再分发的协议；项目正式文件名用英文规则。实际队伍年级、报名组别仍需确认。本轮不选择许可证、不恢复 Git、不公开归档对话或第三方资料。

#### 观察事实：现状和缺口

- 保存的 BD 参数与领航者构建脚本中所列核心字段一致：`xc7z020clg400-2`、输入时钟 33.333333 MHz、FCLK0 100 MHz、32 位低电压 DDR3、533.333333 MHz、兼容配置 `MT41K256M16 RE-125`、UART0/MIO14–15、UART1 关闭、ECG 地址 `0x43C00000`/64K。这里是静态一致性核查，不是硬件适配确认。
- 实际 BD 将 FCLK0 接 GP0、互连和 ECG，ECG 复位由 `rst_ps7_0_100M/peripheral_aresetn` 提供；保存状态为 `validated=true`，本轮未调用 `validate_bd_design`。
- 当前检测器是差分绝对值滑动积分、阈值上穿和不应期的 QRS 候选模块。默认输入有符号 16 位，360 Hz，积分 120 ms（43 点），不应期 200 ms（72 点），能量 24 位。未实现计划中的带通/基线处理或信号质量评估，不能称为完整 Pan-Tompkins 实现。
- 阈值初始噪声/信号估计为 4096/16384，尚无公开标注 ECG 数据校准证据。候选位置减半窗口（21 点）是近似补偿，定位误差必须通过标注对照测量。
- 当前接口测试为 FIFO 深度 2、500 Hz，覆盖 AXI/FIFO、合成阶跃，并用 `force` 注入部分事件；正式 FIFO 默认深度 8。测试能说明接口行为，不能说明真实 ECG 检出率。
- 旧日志中确认 PASS、独立 RTL 综合 0 Errors/0 Critical Warnings、空工程创建完成；日志时间晚于对应源码修改时间，但未提供本次重新运行或完整源码哈希关联。
- 正式目录未发现 Python 软件参考、PS C/H 回放程序、`skill/`、许可证和最终设计报告。计划书仍是待确认草稿。
- 当前目录已移到 `Desktop/ecg_edge`，旧日志和 XPR 的 Project Path 仍指向 `Desktop/fpga/ecg_edge`，旧绝对目录当前不存在。XPR 中两个 RTL 引用是相对路径，脚本按自身路径定位；不能仅凭旧绝对路径断言工程损坏，但当前目录的实际打开/重建尚未验证。
- `.gitignore` 忽略 `tmp/`、`build/` 和所有 `*.rpt`。这是生成物管理规则，但正式交付仍需另行导出和保留经过筛选的资源/时序/验证证据，不能只留下被忽略的原始日志。

#### 分析与取舍

目前主要缺口是算法和真实数据的证据链。先生成 bitstream 可以验证工具链，却不能回答“检测是否正确”。先迁移 PYNQ 或加入 DMA/LSM 会增加环境与模块变量，也不能填补软件参考缺口。

因此建议先保留现有 AXI-Lite 送样方式，建立 PC 数据回放与逐样本对照，暴露算法问题后再作有依据的修改。低采样率下是否需要 DMA，要通过持续吞吐、占用和丢样测量决定。软件参考分两层：按位复现当前 RTL 的定点模型用于查实现一致性；浮点/标准检测基线用于判断算法效果。两者职责不同，RTL 与自身模型一致不等于检出算法准确。

#### 下一步计划与验收条件（尚未实施）

1. **先建立离线数据与参考验证闭环。** 从少量公开 ECG 记录开始，锁定记录、导联、采样率、ADC 基线/缩放/裁剪规则与标注类型，保留来源、许可、校验和。用固定转换生成有符号 16 位样本；开发/测试按记录或受试者分开，参数不在保留测试集上调优。
2. **建立当前 RTL 定点参考和自动对照。** 覆盖差分、历史窗口、定宽算术、阈值更新、初始状态、不应期、事件索引和 RR。导出同一输入下参考轨迹与 RTL 轨迹；失败定位到第一个不同样本/状态。加入连续与有间隔 sample_valid、复位、零/直流、满量程正负跳变、首个事件和窗口边界测试。正常案例验收为数值/事件逐项一致且输入样本计数一致。
3. **建立真实 ECG 指标基线。** 明确一对一标注匹配与时间容差，输出逐记录 TP/FP/FN、灵敏度、阳性预测率、定位误差和 RR/心率误差；容差、首个无 RR 事件、初始化段和漏检处理须预先记录。先如实测当前候选检测器，再根据失败样本决定滤波、阈值和峰值定位改动。暂无承诺准确率。
4. **在当前路径验证可重建性，并做 PS 回放。** 不覆盖已有 `tmp/vivado/ecg_edge`，使用独立临时构建路径；跑接口回归、BD 和整机综合/实现，再生成新 bitstream/XSA。板上阶段前确认实物核心板/底板版本与启动方式。PS 先用 Standalone C 做短样本回放、单消费者读完整事件后弹出，记录提交样本、总事件、出队与丢弃计数；通过板上输出与同输入参考对照验收。
5. **再做候选创新与前端。** 基线可靠后，比较固定检测与信号质量感知策略的干净/受噪表现、漏误检、延迟和资源；无收益则修正方案。AFE/ADC 按匹配资料单独核实，不把通用 AD/DA 例程当 ECG 前端。
6. **同步整理交付证据。** 后续每次实验追加本文；筛选模型协作记录并脱敏，不直接公开原始聊天。把已验证黄金参考对照、事件消费、构建排查等提炼到 `skill/`，补 README 目录对照、正式报告、许可证和可复现证据。未验证经验不包装成通用有效技能。

最近一个阶段的具体验收目标：**同一批公开 ECG 样本可以在 PC 参考与 RTL 仿真中重复运行，自动报告实现差异和标注检测指标。**这部分可以在没有确认实物版本、没有 AFE 的情况下先推进。

#### 本轮结果与限制

完成静态文件、历史日志和本地指南页面核对，形成以上顺序；只新增本过程记录及 `tmp/next_step_review/` 派生阅读文件。没有修复源代码或补写未做实验，未验证当前路径下 Vivado 实际加载与重建，未确认最新赛事公告和实物版本。

### 2026-10-13：上板状态分析与下载流程核查

#### 目标与执行范围

用户询问当前程序上板后的状态及如何烧录，并再次指定 A 盘本地资料目录。本轮读取资料、核查文件并编写操作说明，没有操作实际板卡，Git 仍暂停。用户提供的是资料路径，不能据此推断实物核心板/底板版本或下载器型号。

#### 观察与依据

- 当前 RTL 接收 PS 的 AXI-Lite 寄存器送样；没有串口采样、ADC、显示、用户 LED 控制或 ECG PS 应用。仅下载 bitstream 不会自动得到 ECG 波形或心率输出。当前 PL 时钟与复位依赖 PS FCLK0 和复位网络，须通过匹配初始化流程启动。
- 使用 `rg --files --hidden --no-ignore` 重新检查生成物，找到唯一旧 bitstream `vivado/ecg_edge/ecg_edge.runs/impl_1/ecg_system_wrapper.bit`，大小 4045773 字节，修改时间 2026-10-06 16:41:40；当前 BD 修改时间为 2026-10-13 16:49:48，AXI RTL 为 16:24:46。不能把旧 bitstream 当新版输出。本轮在 vivado/tmp 搜索未发现 XSA 或 ELF。
- 实际阅读 A 盘 Vitis 指南第 2.5 节第 52–58 页、第 7.4–7.5 节第 155–159 页，以及 FPGA 指南 BOOT_CFG 和 JTAG 相关章节；查看 Vitis 第 52/53/55/57/58/157/158 页、FPGA 第 116/119 页渲染。主目录手册：底板 14 针 JTAG 与核心板 6 针口连同一网络；USB_UART 用于串口；P5 跳帽接 PS 收发；BOOT_CFG ON/ON=JTAG、ON/OFF=QSPI、OFF/OFF=SD；Hello World 终端为 115200 8N1 无流控。
- 核对 AMD UG908 2026.1 Hardware Manager 流程及 UG1400 2026.1 平台、应用、启动配置和 Standalone Debug 文档。2026.1 用 Platform/Application Component 和 Debug Settings/Launch Configuration；旧教程界面不能机械套用。新文档明确允许同平台 FSBL 或 Tcl 初始化板卡，并配置 bitstream 与应用 ELF。
- 本机 XSDB 启动文件实际存在于 Vivado/Vitis 的 bin 中。本轮未启动 XSDB 或 hw_server，也未发现或连接实际 JTAG 目标。

#### 现象、尝试与限制

第一次默认 `rg --files` 会遵从 `.gitignore`，看不到旧 bitstream，改用 `--hidden --no-ignore` 后找到文件；因此不把默认列表的空结果写成磁盘不存在。PowerShell 下传递目录 `*` 给 rg 产生无效路径错误，改为直接搜索目录。PDF 渲染出现 Symbol/ArialUnicode 字体提示，实际已打开关键页面核对，接线与启动表清晰可读。部分猜测的 AMD 文档 URL 无法打开，改为从当前正式目录链接读取；未沿用 UltraScale+ 的初始化命令作为 Zynq-7020 步骤。

#### 方案与产出

新增 `docs/board_bringup.md`，分别解释 `.bit`、XSA、ELF、PS 初始化和 BOOT.BIN；给出实物核对、JTAG/串口连接、重建新硬件、Vivado 配置下载、Vitis 初始化并运行应用的步骤。初次上板建议先同平台 Hello World 检查 PS/串口，再用 ECG 回放应用读取参数、送样和消费 FIFO；Hello World 与 DONE 都不能证明 ECG 检测精度。

暂不制作硬件下载脚本或固化镜像：用户当前要求是核查怎么做，且没有确认实物版本、下载器、新 bitstream 或应用 ELF。后续执行前先补齐这些具体条件；不覆盖出厂 QSPI/SD 内容。渲染与提取材料留在 `tmp/board_bringup_review/`。

### 2026-10-13：多人协作规则拆分与当前源码下载前验证

#### 目标、范围与规则变更

用户要求从所贴 Obsidian AGENTS 中适当引入 DeepSeek 约束，区分团队共用与本机专属规则，记录资料位置，然后核查程序以准备下载。本轮修改 `AGENTS.md`，在独立 `tmp/pre_download_20261013_01/` 检查源码并生成当前硬件输出，追加本文；没有修改 RTL、正式构建脚本、现有测试或正式 Vivado 工程，没有执行 Git 或连接硬件。

完整读取附件第 15 节，将授权模式、准确写入清单、当前版本/哈希、唯一补丁、并发变化复核、报错后状态核查、停止/交接与完成证据移为工程化的第 7 节，保留仅对 DeepSeek 系列强制的范围；不移入 Obsidian 排版或插件流程。第 1—6 节共用，第 8 节集中本机项目、A 盘资料、工具路径、板卡未决项与会话 Git 暂停状态。共同构建规则要求路径可迁移，其他成员的 Git 授权不受本机会话自动约束。

修改前备份为 `tmp/backup/agents_before_shared_split_20261013_01/AGENTS.md`，核对 SHA256 一致。源文件初始哈希在检查目录 `before.json`，结束时再次核对源码/脚本/测试未变化；AGENTS 差异、章节范围和基本格式检查通过，记录为 `agents.diff`。没有进行 DeepSeek 实际模型任务验证，不宣称规则成为工具层硬限制。

#### 环境、失败尝试与原因分析

环境为 Windows / Vivado 2026.1，工具在本机 `D:/AMDDesignTools/2026.1/Vivado/bin/`。默认受限环境运行 vivado.bat 时出现 Access is denied，随后 setupEnv/loader 定位错误；RTL 分析能通过，但 xelab 编译生成 C 文件失败（XSIM 43-3409/43-3915）。没有把这些现象当成源码故障或修改安装权限。

保留失败输出和 `interface/` 日志，通过受控权限重试同一源码；Vivado 检测到有效 BASIC 许可证，重试的接口自检和完整构建通过，初次失败与受限执行环境有关。临时检查脚本仅在 `tmp/`，创建独立工程，不覆盖旧工程和既有日志。一次报告检索误把 PowerShell 的 ErrorAction 参数传给 rg，修正检索命令后读到实际报告，没有改变验证结果。

#### 本轮实际完成的验证

- 现有 `tests/tb_axi_lite.sv` 自检通过：AW/W 分开、响应反压、零 WSTRB、FIFO 快照/溢出/满时入出队、非法地址和参数读回，测试深度 2、500 Hz，部分事件受控注入。日志 `interface_retry/xsim.log`。
- 新临时边界 testbench 检查默认 360 Hz/43 点积分：100 个零样本、1000 个满量程正负交替样本（含停顿）、44 个直流样本与复位通过，滑动窗口满量程和为 2818005；包含后续事件发生时的 RR 一致性断言，不能把条件断言当全场景 RR 认证。日志 `detector/xsim.log`。这不是标注 ECG 指标测试。
- 从当前 `Desktop/ecg_edge` 路径新建 PS7/AXI/ECG 工程，BD 验证、完整综合、完整实现、bitstream 生成及 XSA 导出通过。过程在 `build_retry.log`，验证标记 `CHECK_BD_PASS`、`CHECK_SYSTEM_SYNTH_PASS`、`CHECK_BITSTREAM_AND_XSA_PASS`。
- 完整 routed design：WNS +0.329 ns、WHS +0.057 ns、WPWS +3.870 ns，失败端点均为 0；无无时钟或未约束内部端点问题。报告 `timing_summary.rpt`。布局/路由中途曾出现负的估计余量，最终工具优化后收敛，不能把中间估计当最终结果。
- DRC 检查违规数 0，报告 `drc.rpt`。资源 LUT 1309、FF 1663、BRAM Tile 0、DSP 0，报告 `utilization.rpt`。打包、参数依赖分析及未加载端口优化等警告仍存在，不声称所有警告消除。
- XSA ZIP CRC 完整性通过，内嵌 bitstream 与单独输出的 SHA256 一致；源文件与开始快照一致。产物清单及哈希在 `artifacts.json`。

#### 产物、结论与下一步

当前检查输出：`tmp/pre_download_20261013_01/ecg_system_candidate.bit` 与 `ecg_system_candidate.xsa`，独立工程为该目录 `build/ecg_check.xpr`；本轮没有替换 10 月 6 日旧 bitstream。完整报告见同目录 `report.md`。这些是当前代码的可下载候选输出，非板上验证成果。

本轮未发现阻止所测接口行为、默认检测器边界及整机实现/生成 bitstream 的故障；未修改设计。仍缺 ECG PS 应用 ELF、真实 ECG 标注指标、采集/显示链路和实物版本确认。单独 JTAG 配置只能检查下载/DONE，需按匹配 XSA 初始化 PS 后运行送样应用，才有检测结果。下一次实物测试应先核对核心板/底板版本和下载器，使用上述新版产物，保留初始化、串口及寄存器结果；没有做实际 JTAG 下载、PS 初始化、Flash/SD 写入或人体采集。

### 2026-10-13：首次连接 JTAG 未发现目标器件

用户提供 Vivado Messages 截图，显示 `[Labtools 27-2269] No devices detected on target localhost:3121/xilinx_tcf/Digilent/...`，提示检查接线与目标板供电并重连硬件服务器。观察事实：工具已枚举 Digilent 下载器目标，但未识别链上器件；尚无 bitstream 下载成功证据。不能由该截图判定是 RTL、DDR 配置、驱动或板卡损坏。

建议先检查板卡独立供电和电源指示、断电后核查 JTAG 插口/方向/连接，然后上电重新连接目标。截图建议的 `disconnect_hw_server`、`connect_hw_server` 和 `open_hw_target` 仅交由用户在 Vivado Tcl Console 操作，本助手未执行硬件命令。若仍不识别，可依据 AMD UG908 2026.1 Troubleshooting a Hardware Target 检查/降低 JTAG TCK 频率。实物接线、供电、重连及降速是否有效均待用户实际反馈。

### 2026-10-13：USB 供电后识别器件与 Hello World 板上运行

#### 用户实际操作与观察

用户表示连接 USB 并打开电源开关后，Vivado 识别出 `arm_dap_0` 和 `xc7z020_1`；之后确认新版 bitstream 下载步骤正常。此前 JTAG 未发现器件的问题随用户补充供电/打开开关而解除，尚未单独测量供电各路电压，不能据此进一步认定所有电源指标通过。

用户在 Vitis 2026.1 创建并构建 `ecg_platform`、`hello_world`；截图中平台状态为 Platform Build Finished successfully。串口设为 115200，用户直接点击左侧 Run，提供输出末尾为 `Hello World` 和 `Successfully ran Hello World application`。这是本项目平台上的 PS Hello World 应用执行并经 UART 输出的板上证据；不是 ECG 送样或 QRS 检测验证。

#### 本地配置核查

本轮实际读取 `hello_world/src/helloworld.c`，其中确实打印上述两个字符串。读取 `hello_world/_ide/launch.json`：本地 zynq/baremetal 启动、resetSystem=true、programDevice=true，使用 `hello_world/_ide/bitstream/ecg_system_candidate.bit`；初始化选择 Tcl（isFsbl=false），runPs7Init=true、runPs7PostInit=true；下载 `hello_world/build/hello_world.elf` 到 `ps7_cortexa9_0`，stopAtEntry=false。UART 是输出通道，Run 配置仍通过本地调试连接启动硬件应用，不是把 ELF 经串口烧录。

该启动配置中的 FSBL 路径是备用选项，当前使用的是生成的 `ps7_init.tcl`，不能误写成此次通过 FSBL 初始化。用户把 Vitis 组件实际创建在项目根目录的 `ecg_platform/`、`hello_world/`，与先前建议的 tmp 工作区不同；本轮仅核查，不移动用户已建组件。

串口前段含 U-Boot 2018.01、从 QSPI 读取 `navigator_7020_wrapper`（2018.3 / 2021-07-09）、SD 初始化及 PHY 错误，是原有启动软件输出。`Xilinx Zynq ZC702` 是该 U-Boot 的软件板级标识，不能推翻用户确认的领航者实物型号；未修改或修复原有 QSPI 环境。时间顺序依据用户提供的输出，未经独立重现每次复位行为。

#### 结论与下一步

可以确认用户侧已取得器件识别和 Hello World 板上串口输出。已具备下一阶段测试条件：让 PS 读取 ECG 配置寄存器（360 Hz、120 ms、200 ms），再送入受控数字样本并核对 FIFO 的 QRS/RR/事件序号及丢弃计数。该读写测试、真实 ECG 准确率和 AFE/ADC 采集仍未完成。此次只核查并记录用户证据，没有修改应用、运行硬件命令或操作 Git。

### 2026-10-13：通用下载教程与 Vitis 工作区归置

用户要求编写通用教程并移除根目录新增的两个组件，随后明确回复 Vitis“已关闭”。本轮范围为 `ecg_platform`、`hello_world` 的可恢复归档、新工作区重建及教程；未修改 RTL、PS7 参数或原始下载资料，未运行 Git 或板卡下载命令。

#### 原因与取舍

实际读取平台和应用的 `vitis-comp.json`、应用源码、`_ide/launch.json`。平台输入 XSA 是 `tmp/pre_download_20261013_01/ecg_system_candidate.xsa`；组件却位于仓库根目录，启动配置用 `${workspaceFolder}` 引用根目录下两个组件。说明原创建流程的工作区/组件 Location 选在根目录。前面的指导没有充分强调创建向导的 Location，通用教程补齐这个检查点。

不直接剪切带旧 CMake 缓存的目录作为最终工作区。先将两个原组件可恢复地移到 `tmp/backup/vitis_root_components_20261013_01/`，对 2058 个文件记录路径、大小和 SHA256；移动前后哈希全部一致，清单为该目录 `manifest_before.json`。原根目录 `_ide` 等其他元数据保留，避免扩大清理范围。

#### 本机重建与核查

环境 Windows / Vitis 2026.1。依据安装目录 `cli/examples/embedded/platform_creation_standalone.py` 和 `platform_uc4_zynq.py` 的 Python API，在 `tmp/vitis_bringup` 用同一份自定义 XSA 重建 `ecg_platform`，domain 为 `standalone_ps7_cortexa9_0`；再创建 Hello World 应用，分别 Build。未使用官方 zc702 预设。一次性脚本为 `tmp/rebuild_vitis_workspace.py`，拒绝覆盖已有工作区。

构建日志为归档目录 `rebuild.log`，出现 `Build Finished successfully` 和 `VITIS_WORKSPACE_BUILD_PASS`，工具进程退出码 0。新生成 ELF 的 text/data/bss 为 24504/1424/22984 字节，仅是构建大小，不是性能指标。新应用的 `helloworld.c`、`platform.c`、`platform.h` 与归档原文件哈希相同；新 CMakeCache 的源码根为 `tmp/vitis_bringup/hello_world/src`。

恢复运行配置时先采用“不覆盖已有文件”的保护检查，发现新工作区已经存在 launch.json、bitstream 和 psinit，停止该复制动作并重新读取实际文件，没有覆盖。随后核查现有配置仍使用 Tcl 初始化、系统复位、配置 PL、Cortex-A9 核 0、对应 ELF 且不停止入口；所有引用文件均存在。新工作区复制本机 Local target 的 `.peers.ini`（仅在目标缺失时）。新工作区 bitstream SHA256 为 `C12F39430FAA114B9D9A7D85628FC5020C48F1BF368A4E2E87CC4AC4A9DCB650`，与本次硬件候选输出一致。核查摘要为归档目录 `verification.json`。

#### 文档与验证边界

新增 `docs/zynq_jtag_uart_tutorial.md`，正文按通用工具流程组织，说明 bit/XSA/ELF、独立工作区与 Location、硬件识别、平台/应用 Build、115200 串口、PS 初始化、Run/Debug、旧 U-Boot 输出及断电后启动的区别；项目当前路径放在末节。依据 AMD UG1400 2026.1 平台创建、示例应用、Serial Monitor 和启动配置章节在线复核菜单，README 增加入口。

根目录两个组件已不存在，原组件完整保留，新工作区本地构建通过，启动引用有效。此次未打开 IDE 界面或重新上板；用户此前提供的 Hello World 成功输出属于迁移前板上证据。用户下次启动 Vitis 应选择本项目 `tmp/vitis_bringup` 工作区，再打开串口并 Run；迁移后的运行结果和 ECG 接口功能仍待实测。

### 2026-10-13：无 SD 卡时 QSPI 自启动流程核查

用户询问如何把程序固化到板载 QSPI。本轮只核查并说明步骤，未获设计修改或实际写 Flash 指令，未生成启动镜像、修改 PS 配置或执行硬件命令。

核对当前 XSA 内嵌 HWH，`PCW_EN_QSPI=0`、`PCW_QSPI_PERIPHERAL_ENABLE=0`；当前脚本也未配置 QSPI。新平台 FSBL 和 Hello World ELF 已存在，但此前成功的运行采用 Tcl 初始化，仅证明 JTAG Hello World，不能直接推导这份硬件配置能够 QSPI 自启动。

阅读本地 Vitis 指南第 7.5 节相关文字，查看 `tmp/board_bringup_review/vitis_158.png` 的实际启动模式表：JTAG 为 BOOT_CFG 1=ON、2=ON；QSPI 为 1=ON、2=OFF。指南第 7.6 节明确固化例程在硬件平台增加 QSPI 等外设并重新导出。在线核查 AMD UG1400 2026.1 Creating a Boot Image 和 Programming Flash：菜单 Vitis → Create Boot Image / Program Flash，启动分区使用 FSBL、bitstream、应用，Flash 界面含 Image、Offset、Flash Type、Init File 和 Verify after Flash。

当前前置工作应先按匹配核心板原理图和官方例程启用 QSPI，再重建 bit/XSA/平台/FSBL/应用。后续生成 BOOT.BIN 并从 JTAG 模式写 QSPI 的启动位置，断电切到 QSPI 后验证串口；写入启动区域会替换原有引导内容，需要了解保留/恢复方案。上述流程尚未实际执行，不能将现有候选产物宣称为已验证 QSPI 镜像。

### 2026-10-13：合并补录早期工作区归并与领航者修复记录

以下内容迁自原 `docs/workspace_migration.md`，记录的是早期修复阶段，原有结论和证据路径保留，不代表本次重新运行验证。该阶段环境为 Windows / Vivado 2026.1；当时项目根目录为 `Desktop/fpga/ecg_edge`，当前已经迁至 `C:/Users/23006/Desktop/ecg_edge`。下文“没有做整机实现、生成 bitstream 或上板”等仅限当时阶段，后续整机构建和用户 Hello World 板上输出见本文前面的对应日期任务。历史剩余工作也不是当前进度清单。

日期：2026-10-13。

#### 统一项目根目录

`C:/Users/23006/Desktop/fpga/ecg_edge` 是现有仓库及统一项目根目录，外层 `Desktop/fpga` 只保留此目录。没有执行 Git 命令，没有暂存、提交、推送或修改 `.git`。没有迁移或修改 `Desktop/VHDL` 的内容。

| 原外层内容 | 新位置 |
| --- | --- |
| `AGENTS.md` | 项目根目录 `AGENTS.md` |
| `baidu_netdisk_review.md` | `docs/materials_review.md` |
| `tmp/` | 项目根目录 `tmp/`，含备份、审查报告、索引、脚本和预览 |
| AMD 2026 选题指南 PDF | `docs/reference/amd_track_guide_2026.pdf` |
| Vitis 2026.1 中文手册 PDF | `docs/reference/vitis_embedded_2026_1_zh.pdf` |
| 根目录 `.Xil`、`vivado.jou` | `tmp/legacy_vivado/` |

原始文件采用移动，没有删除。`ecg_edge/vivado/ecg_edge` 原有工程目录保持原位置，避免破坏 Vivado 相对路径。A 盘下载资料仍在原来的 D 盘目录，没有把整个资料盘塞进仓库。

#### 忽略范围

`.gitignore` 排除项目 `tmp/`、Vivado 缓存/生成/运行目录、bitstream/XSA/ELF、中间网表、日志和波形、本机 IDE、Python/Node 环境及本地凭证。`docs/reference/` 是本地第三方资料，也默认忽略。

正式 RTL、测试、Tcl/PowerShell 构建脚本、README、项目计划、寄存器接口、XPR/BD/XCI 等保留为项目文件。忽略规则不能从 Git 历史或现有索引中自动移除文件，本轮未操作这些状态。

#### 修复内容

1. 现有 BD 与新构建脚本改为 UART0/MIO14–15，关闭 UART1；DDR 改为 `DDR 3 (Low Voltage)` 和兼容配置 `MT41K256M16 RE-125`。
2. `build_navigator_ecg_system.tcl` 负责领航者配置。旧 AC7020 名称脚本仅作兼容入口，转发到新脚本。
3. 构建脚本可从没有 BD 的新工程创建 PS7/AXI/ECG 完整系统；按脚本自身路径定位源码，支持现有工程和 tmp 内新工程。
4. 刷新 RTL 模块使用项目 IP 对象；刷新后重新获取 BD 对象，避免沿用失效句柄。此行为经 Vivado 2026.1 实际运行核实。
5. QRS 事件保存到默认 8 深度 FIFO，位置/RR/序号保持同一事件的快照；队列满时保留已有事件，显式记录溢出及丢弃数。
6. 解码完整地址，未实现、未对齐或向只读地址写入返回 SLVERR，没有低 6 位地址镜像副作用。
7. AXI 包装层传入采样率/积分窗口/不应期参数，增加只读参数寄存器；RR 使用与事件位置一致的非负回移索引计算。
8. 新增正式接口自检 `tests/tb_axi_lite.sv` 和 `scripts/run_rtl_tests.ps1`。详见 [寄存器说明](../register_map.md)。

#### 验证结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| RTL 行为自检 | 通过 | `tmp/rtl_tests/xsim.log` 的 PASS 标志 |
| AW/W 分开、响应反压、零写选通 | 通过 | 上述自检 |
| 事件快照、FIFO 满溢出、同时出入队、序号 | 通过 | 上述自检，测试深度 2，包含受控事件注入 |
| 非法/未对齐地址没有采样副作用 | 通过 | 上述自检 |
| 参数采样率 500 Hz 传入并可读回 | 通过 | 上述自检；正式 BD 默认仍为 360 Hz |
| 实际现有 BD 配置与验证 | 通过 | `tmp/validate_navigator.log`；保存 BD 的 validated=true，UART/DDR 值已核查 |
| 从空目录创建完整工程 | 通过 | `tmp/rebuild.log`；工程在 `tmp/vivado/ecg_edge` |
| ECG RTL 独立综合 | 通过 | `tmp/rtl_synth.log` 的 `ECG_RTL_SYNTH_PASS`；0 Errors、0 Critical Warnings |

Vivado 仍有 SystemVerilog 模块打包支持、内部 localparam 依赖分析和未使用信号等警告；这些没有阻止本次验证和独立综合，不等于所有警告已消除。

没有做修复后整个系统的实现/时序收敛、新 bitstream 生成、XSA 导出、PS 应用构建、下载或板上运行。原 `.runs/impl_1` 中的 bitstream 是旧配置，不能当作修复后的输出使用。独立 RTL 综合不代表整机时序通过，合成样本/事件测试不代表真实心电检测准确率。

#### 备份和剩余工作

修改前的 RTL、脚本、README、忽略文件、XPR、BD 保存在 `tmp/backup/ecg_before_navigator_fix_20261013/`。核查报告在 `tmp/engineering_audit/report.md`，它描述修复前状态。

下一阶段仍需核实实物核心板/底板版本及实际采样率，重建整机结果和硬件平台，完成 PS 样本回放程序与软件参考模型，再验证真实 ECG 数据和采集前端。Git 继续暂停，直到用户明确恢复。

### 2026-10-13：文档合并与入口修正

#### 目标、取舍与实际修改

用户授权合并上板说明和历史迁移记录，明确要求 `docs/materials_review.md` 不动。Windows 文件编辑环境下，将原上板说明的领航者接线、启动拨码、ECG 验收和来源定位合并到 `docs/如何下载.md`，通用下载流程沿用教程前半部分；去掉已过时的“只有旧 bit、没有 XSA/ELF”现状描述。迁移表、忽略范围、修复细节、原验证表和备份位置在上一节保留，并标明历史阶段，避免覆盖其他成员记录。

原 `docs/board_bringup.md` 和 `docs/workspace_migration.md` 原样归档到 `tmp/backup/docs_merge_20261013_01/docs/`。README 改用实际存在的 `docs/计划.md`、`docs/如何下载.md` 和 `lykzr.md` 入口，更新为已有构建记录和用户 Hello World 输出所支持的验证阶段；`myself.md` 仅修正下载说明路径。`docs/materials_review.md` 和 `docs/register_map.md` 均保持原样。

#### 检查与边界

备份目录保存修改前文件、SHA256 清单、局部差异和检查结果；脚本在 `tmp/doc_merge_20261013/merge_docs.py`。写入前核对当前文件字节，追加前保护 `lykzr.md` 原内容；发生并发变化时停止并重新读取。检查本次入口和 Markdown 本地链接，核对两份归档与原文件字节一致，核对资料入口和寄存器说明哈希不变。检查结果见备份目录 `verification.json`。

这次只修改文档并归档两份旧文档，没有改 RTL、BD、PS7、XDC 或工程构建脚本，没有运行 Git、仿真、综合、实现、IDE 或硬件命令。整机构建和板上输出来自既有记录，不是本轮新实验；QSPI 工作由原聊天继续推进，本轮没有宣称其完成。

### 2026-10-13：QSPI 配置修改与 Hello World 启动镜像生成

用户明确授权“那你改吧，如果有我改不了的踢我”。本轮由本机 Codex 修改 `scripts/build_navigator_ecg_system.tcl`，仅增加 QSPI 参数和依据注释；RTL 两文件哈希与先前验证快照相同。读取官方 Vitis 指南第 7.1—7.6 节相关内容，查看配置图与核心板原理图实际页面，使用 tar 从原始 RAR 提取官方 `6_axi_gpio_fsbl` 的 system.bd 到独立 tmp 目录并逐项核对 QSPI 参数。7z 的 WindowsApps 启动别名不可访问，未改权限或安装软件；改用已有 tar 正常完成资料提取。PDF 渲染提示字体替代警告，实际配置图及原理图可读。

依据：核心板原理图 Bank500 页 MIO1 为 CS、MIO2—5 为 D0—D3、MIO6 为 SCK；Flash 页单颗 W25Q256FV、3.3V；官方 BD 为 QSPI enabled、Single SS 4bit IO、MIO1..6、IO PLL/200MHz、反馈时钟关闭、第二数据组/片选关闭。只启用 QSPI，不加入无 SD 卡时不需要的 SD 控制器。修改前脚本保存在 `tmp/backup/qspi_boot_20261013_01/build_navigator_before.tcl`；局部文件对照仅新增这组参数和说明。

独立输出在 `tmp/qspi_boot_20261013_01/`，Vivado 工程为 `build/ecg_qspi.xpr`。`check_build.tcl` 在实际 BD 中断言 QSPI 开启，完成 BD 验证、综合、实现、bitstream 和含 bit 的 XSA 导出，退出码 0。最终 WNS +0.329 ns、WHS +0.057 ns、WPWS +3.870 ns，失败端点 0，DRC 无违规；完整报告为 timing_summary.rpt、drc.rpt，过程为 build.log。未修改现有 Vivado 工程或旧 JTAG 产物。

同目录 `build_software.py` 使用新 XSA 构建 `vitis_workspace/ecg_platform` 和 `hello_world`，平台及应用成功，日志 `software_build.log` 出现 QSPI_SOFTWARE_BUILD_PASS，退出码 0。BSP `xparameters.h` 检出 XPAR_XQSPIPS_NUM_INSTANCES=1、QSPI_BASEADDR=0xe000d000、connection mode=0（single）；FSBL 已包含新硬件的 QSPI 支持。软件构建出现 CMake 长路径及编译警告，最终通过，没有当作零警告。

`boot.bif` 顺序为 [bootloader] FSBL、新 bitstream、Hello World ELF。Bootgen 2026.1 生成 `BOOT.BIN` 成功，镜像 4169224 字节，小于 32MiB Flash；bootgen -read 成功读取头表，width_detection=0xaa995566、image_id=0x584c4e58、输入文件顺序正确。应用 ELF 有三个加载分区，总加载分区数 5；不误认为多出两个应用。镜像 SHA256：4B902DB837F8BB326F81775B745F651011403655D677EF0893D550C425F21A38。新 XSA 内嵌 HWH 确认 QSPI enabled，内嵌 bit 与单独输出 SHA256 一致，启动配置引用存在。全部产物大小/哈希及验证阶段在 artifacts.json。

文档并发期间发现其他会话将教程改名并归并上板/迁移说明。本轮重读当前 README、`docs/如何下载.md` 和 lykzr 末尾，保留其他成员变更；早先修改的 board_bringup 后由整理会话归档，不重新恢复该文件。实际教程第 12 节加入 QSPI 流程，末尾第 16 节追加本次最终状态；README 使用当前名称和 QSPI 产物入口。用户交接另在产物目录 READY.md，明确 Program Flash 字段及拨码操作。

没有连接板卡或写 Flash，没有备份原有 QSPI，也没有断电自启动实测；生成的是 Hello World 固化候选，不是 ECG 应用。用户剩余动作：JTAG 模式下 Program Flash 写 BOOT.BIN 到 offset 0，类型 qspi_single，Init File 选本次 fsbl.elf 并 Verify；成功后断电切 BOOT_CFG 1=ON、2=OFF，再看 115200 串口。该写入将替换原有引导区域，用户执行前应明确是否保留原厂启动内容。Git 保持暂停。

### 2026-10-13：构建目录与正式发布归档约定

用户认可“构建放 tmp、验证后的发布文件放 releases/<版本>”，要求写入并询问工程大小。本轮更新 AGENTS.md 开头和第 5 节、新建 releases/README.md、README 增加目录入口。发布仅复制已验收的同组镜像及匹配 FSBL、必要配套文件、SHA256 清单和验收记录，不复制整套缓存、不覆盖旧版本、不自动清理原工作区。现有二进制忽略规则保留；本地归档不等于 Git 共享或远端发布。

Windows 文件长度统计快照在 tmp/release_size_20261013.json：rtl/scripts/tests 共 34992 字节（约 34KiB）；本次 Vivado 工程 45.73MiB，Vitis 工作区 46.30MiB，本次 QSPI 构建目录总计 102.28MiB；BOOT.BIN 3.98MiB，与匹配 FSBL 合计 4.32MiB。整个工作区约 458.25MiB，排除 .git；tmp 约 408.39MiB，主要含历次构建、备份和资料索引。统计是文件长度合计，不是分配块占用，也不是未来工程体积上限。

重新读取实际文件，核对 README 的本地链接和新增文件编码。此次仅写归置规则及记录，未移动已完成构建、未复制候选镜像为正式发布、未删除文件或修改设计，没有操作 Git。当前 Hello World 候选仍待 QSPI 断电自启动验收，验收后才按该约定形成正式版本目录。

### 2026-10-13：首次 QSPI 烧录擦除成功、写入前临时文件失败

用户提供 Program Flash 2026.1 日志：BOOT_MODE=0（JTAG），匹配 FSBL 已运行，工具 mini U-Boot 在 OCM 中识别 w25q256/32MiB；sf erase 0 400000 显示 4194304 bytes Erased OK。Program Operation 在 0% 失败，明确错误为 Could not create temporary file D:\AMDDesignTools\2026.1\Vitis\bin\xicom_zynq_bin21344。观察事实是起始 4MiB 已擦除、镜像尚未成功写入和校验，不是文件容量超限；Flash Mismatched 为此前警告，实际终止错误是临时文件创建失败。hw_server 最初连接失败后已自动启动并连接，也不是本次终止点。

本轮读取安装目录 program_flash.bat 与 program_flash -help（只帮助，不连接板卡），确认 2026.1 支持 qspi-x4-single、-f、-fsbl、-offset、-verify、-url。帮助输出保留在 tmp/qspi_boot_20261013_01/program_flash_help.txt。建议用户保持 JTAG，使用 PowerShell 切换到项目可写产物目录，再调用该工具完成同一镜像的编程和校验；根据路径推断 GUI 调用的工作位置在不可写安装目录，但该绕开安装目录的办法尚待用户实际重试验证。未修改安装权限、未要求全盘擦除，也未由本助手执行 Flash 命令。不能把原有 QSPI 引导状态描述为仍完整；起始区域已擦除，需成功重写后再切 QSPI 测试。

### 2026-10-13：QSPI 写入后校验成功，待断电自启动验收

用户从项目可写目录运行 Program Flash，并在一次 Ctrl+C 中断后重试。最新提供日志末尾：cmp.b FFFC0000 FFFC8000 1E08、Total of 7688 byte(s) were the same、Verify Operation successful，校验阶段报告耗时 38 秒。工具报告本次校验成功；7688 字节是日志中最后一个比较块，不把它误写为整个镜像仅有 7688 字节。命令执行与板卡操作由用户完成，本助手未执行硬件写入。

先前安装目录临时文件错误未在这次成功校验的末尾再次出现，说明用户侧已取得重试成功结果；是否完全由工作目录造成仍未独立复现。此次证据支持写入后工具校验完成，不等同于 QSPI 自启动验收。下一步用户断电切 BOOT_CFG 1=ON、2=OFF，打开 115200 串口再上电，不点击 Run；自动出现 Hello World 后才能归档为通过自启动验收的发布版本。当前候选保持原位置，未发布或移动。

### 2026-10-13：串口 COM14 输出与复位操作说明

用户提供 COM14/115200 输出：Hello World、Successfully ran Hello World application，连续出现两组；并反馈应该直接提醒 reset。按会话上下文，记录为用户复位后重新观察到应用输出，不把连续两组打印自行解释成算法故障。先前已提供 Flash Verify Operation successful；本次补充串口应用运行证据。具体完整断电上电过程未由这条反馈单独明确，不将 PS 复位观察扩大为掉电保持全流程验收。

纠正指导顺序：对已经处于 QSPI 启动模式的板子，打开串口后按 PS 复位即可重新观察只打印一次的 Hello World；无需每次开关电源。完整断电自启动验收另外进行。提醒 PS 复位与用户按键不同，JTAG 易失应用复位后的重跑不能照搬 QSPI 操作。教程 docs/如何下载.md 串口节补入该说明，未改硬件、镜像或运行配置。

### 2026-10-13：发布 latest，历史忽略但不删除

用户明确要求“然后release那个啊，只留最新版本，其他的都ignore掉但不删除”。本轮据此将当前 Hello World/QSPI 文件复制到 releases/latest/，保留原 tmp 工作区及全部历史文件；当前首次建立 latest，没有旧 latest 需要迁移。后续更新约定为先将旧 latest 可恢复归档到 releases/history/<版本>/，不覆盖历史、不删除。

原构建清单中的 BOOT.BIN、FSBL、bit/XSA、应用 ELF 的现有哈希全部匹配。发布包共 9 个文件，约 8.61MiB，版本号 20261013-hello-world-qspi-v1；含上述 5 个二进制、boot.bif、README.md、validation.md、artifacts.json。发布 BIF 改为目录内相对路径，使用本机 Bootgen 2026.1 重打包至 tmp/releases_latest_repacked_20261013.bin，成功且与发布 BOOT.BIN SHA256 完全一致。镜像哈希仍为 4B902DB837F8BB326F81775B745F651011403655D677EF0893D550C425F21A38。重打包日志在 tmp/releases_latest_repack_20261013.log；未操作板卡。

修改 .gitignore，在原有全局忽略规则后仅放行 releases/README.md、latest 目录及 9 个明确交付文件；其他发布路径及 latest 中未列出的内容默认忽略。更新 AGENTS.md 和 releases/README.md 以用户最新选择替代先前多版本默认规则，README 改用 latest 入口，下载教程追加第 18 节。配置修改前备份为 tmp/backup/releases_latest_policy_20261013_01/；重新读取实际文件并校验发布哈希、白名单、文档链接和编码。一次 PowerShell foreach 直接接管道产生语法错误，改为先收集结果变量后正确完成只读校验，没有进行部分复制或覆盖。

清单逐项区分：硬件/软件/镜像检查通过，烧录校验与复位后串口为用户提供的通过证据；完整断电启动未单独确认，ECG 功能未验证。用户本轮授权按这个实际范围归档，不将复位证据补写为掉电验收。Git 持续暂停，未调用 Git 或修改索引；忽略规则只影响未跟踪文件，已跟踪旧文件不能据此自动取消跟踪，此轮也未提交、推送、上传远端。

### 2026-10-13：确认 GUI 烧录临时文件失败的工作目录原因

用户询问是否能恢复图形界面烧录，以及每次是否阅读全部 Markdown。本轮核查本机安装文件和快捷方式，没有运行硬件写入。

直接证据：开始菜单 `AMD Adaptive SoC and FPGA Tools/Vitis 2026.1/Vitis 2026.1.lnk` 的目标为安装目录 bin/vitis.vbs，WorkingDirectory 为 D:/AMDDesignTools/2026.1/Vitis/bin；该目录 ACL 的普通 Users/Authenticated Users 为 ReadAndExecute，没有写入权限。安装包 `ide/electron-app/win64/resources/app/node_modules/@rigel/project/lib/node/program-flash-server.js` 的 programFlash 使用 child_process.spawn(program_flash.bat,args,{shell:true})，未指定 cwd，继承 IDE 后端工作目录。GUI 失败日志正是在 bin 下无法创建 xicom_zynq_bin 临时文件；用户从可写项目目录执行同一烧录工具后获得校验成功。这些证据支持本机启动目录与权限组合是故障原因，而非镜像太大或必须永远使用命令行。

读取 vitis.vbs，发现它相对调用 vitis.bat，直接把原快捷方式 WorkingDirectory 改到工作区可能无法找到该批处理。读取 vitis.bat 与 setupEnv.bat，GUI 启动分支没有强制 cd 回 bin，setupEnv 的目录探测 pushd/popd 成对恢复。建立本机专用 tmp/vitis_launcher/open_vitis.vbs，以绝对路径调用 vitis.bat -w 工作区，先设 WshShell.CurrentDirectory 为当前可写 Vitis 工作区；配套 Open-Vitis.lnk 指向此入口。文件只用于启动 IDE，不烧录、不修改安装目录、权限或系统快捷方式。

默认受限运行 cscript --check 因读取设置 Access is denied；随后申请受控权限执行同一 --check，通过并打印正确工作目录与 launcher，退出码 0，没有启动 IDE。快捷方式回读 target/args/workingDirectory 正确。图形界面再次烧录尚未执行，不能把入口检查写成 GUI 实测成功；用户下次需关闭已有 Vitis 后使用新入口，避免旧进程仍继承原目录。

文档阅读原则解释：每项工程工作先读当前适用约束、相关当前文件和最近记录；计划、寄存器、资料说明、教程按任务关联读取，不宣称每次逐字通读所有 Markdown。事实以实际代码/配置/工具日志和用户板上证据为准，不创建额外重复说明文档。本轮仅在已有教程和本机配置追加定位及启动入口，当前 ECG 业务链路尚未全部验证。

### 2026-10-13：修改原 Vitis 开始菜单快捷方式的工作目录

用户明确选择“改启动工作目录更合适”。本轮备份原系统级 Vitis 2026.1.lnk 到 tmp/backup/vitis_shortcut_20261013_01，副本哈希与原始一致。原链接位于 C:/ProgramData/Microsoft/Windows/Start Menu/Programs/AMD Adaptive SoC and FPGA Tools/Vitis 2026.1，原目标 vitis.vbs，相对启动器不适合只改起始位置。

首次保存因系统级文件写权限失败，回读及哈希确认未变；受控工具执行权限不等同于 Windows 管理员。随后准备明确范围的辅助脚本 tmp/vitis_launcher/fix_startmenu_shortcut.ps1，通过 Windows RunAs/UAC 启动管理员助手。结果 shortcut_fix_result.json success=true，再次独立读取实际 .lnk，目标为绝对路径 D:/AMDDesignTools/2026.1/Vitis/bin/vitis.bat，参数 -w 指向当前软件工作区，WorkingDirectory 为 C:/Users/23006/Desktop/ecg_edge/tmp/qspi_boot_20261013_01/vitis_workspace，WindowStyle=7（启动批处理窗口最小化），原图标保留。

仅修改快捷方式，没有改安装目录 ACL、工具脚本、设计或烧录文件；未启动 IDE 或写 Flash。myself.md 更新本机状态。用户下次先关闭现有 Vitis 后从开始菜单重开，才能使用新进程工作目录；图形界面再次烧录仍未实测，不能仅凭链接回读宣称全流程通过。原始快捷方式与额外本机启动入口均保留，Git 未操作。

### 2026-10-14：PS 配置读回与真实样本 FIFO 自检应用

用户引用并确认下一阶段 PS→ECG 接口验证，本轮编写 software/ecg_smoke/main.c，新增 scripts/build_ecg_smoke.py、scripts/run_ecg_smoke_test.ps1、tests/tb_ecg_smoke.sv；README 增加应用入口，现有下载教程增加第 20 节，没有新增重复 Markdown。读取当前 AGENTS/myself、register_map、检测器与 AXI RTL、现有接口 testbench、安装目录 BSP xil_io.h 及官方 Vitis Python 示例后实施；未修改设计、现有硬件工程、Flash 或 releases/latest。

检测器实际参数 360Hz/120ms/200ms：窗口43点、回移21点、不应期72点。测试先检查基地址0x43C00000的配置和初态，再100个零、4个周期360点的交替±20000脉冲；预期位置79/439/799/1159，RR首0后360，序号1—4，读快照后弹出。第二段12周期不消费，保留8个、丢4个；队首1519/360/5保持，事件累计16。清溢出bit不清丢弃数、依序弹出、空队列读0。总送样5860，快速写AXI并用DATA_SYNC排序，脉冲后usleep(10)等待流水线再读能量；不是360Hz墙钟实时采集，也不是真实ECG指标测试。

真实样本仿真不 force 检测事件。首次命令级仿真在 tmp/ecg_smoke/simulation 通过；新增正式可复现仿真脚本后运行至 tmp/ecg_smoke/rtl_check，日志出现 PASS ECG_SMOKE real samples，退出码0。实际检测器、符号样本能量、事件字段、队首保持、FIFO满丢弃/清提示/消费均符合预期。仿真使用的硬件与当前源码相同，但不是板上证据。

使用 latest 匹配 XSA，在独立 tmp/ecg_smoke/vitis_workspace 新建平台及 empty_application/ecg_smoke，核0 standalone。第一次平台和应用均已编译链接，末尾核对脚本误假设 import_files 将 main.c 放src；实际2026.1默认导入组件根，UserConfig编译../main.c，故文件路径检查报错。原工作区和日志可恢复归档 tmp/backup/ecg_smoke_initial_20261014_01；修正共享脚本核对位置后从空目录重跑，日志 tmp/ecg_smoke_build.log 出现 ECG_SMOKE_BUILD_PASS，工具退出码0。应用ELF169936字节，text/data/bss=31885/1436/23028；正式main.c与实际编译副本哈希一致，不把首轮末尾异常误认成应用未生成。

读取新launch.json：resetSystem和programDevice均true，Tcl init/post-init启用，核0下载ecg_smoke.elf且stopAtEntry=false。所有引用存在，bit哈希与latest匹配。本机Local连接配置在缺失时从此前成功工作区复制到新工作区；没有控制IDE或硬件。没有软件复位寄存器，因此运行必须重新配置PL才保证初态（含7168初始阈值）。启动入口仍打开先前工作区，教程要求本次主动切换新工作区，并打开COM14/115200后Run。

源文件、ELF、现有发布镜像哈希及验证状态在 tmp/ecg_smoke/artifacts.json。latest BOOT.BIN仍为4B902DB837F8BB326F81775B745F651011403655D677EF0893D550C425F21A38，没有替换Hello World。未运行PS应用上板、未写Flash、未更新发布版本或操作Git；待用户提供BEGIN到最终PASS/FAIL串口日志后才能判断真实PS→AXI→检测器→FIFO链路。若卡在首次MMIO读，需查匹配bit/PS初始化/时钟复位，不能以本地仿真或构建替代实物诊断。

### 2026-10-14：逐周期整数参考模型与 RTL 对照

用户授权先实现软件参考模型，并特别要求记住 smoke 尚未测试。本轮在 README、下载教程及对照报告明确记录 smoke_board_test=NOT_TESTED；沿用 tmp/ecg_smoke/artifacts.json 的 boardExecution=NOT_EXECUTED，没有把假设测试完成转成实际结果。参考模型不改变这个边界。

阅读当前检测器完整源码与 AXI/FIFO 的更新逻辑、寄存器定义、项目计划对应软件参考阶段、最新过程记录和已有 smoke 状态。新增 software/reference/ecg_reference.py（仅 Python 标准库）：Config、Detector.tick、状态快照、CSV回放。实现差分绝对值、滑动积分、噪声/信号估计、阈值上穿和不应期；所有组合判断先用旧状态，之后非阻塞语义更新；能量位宽回绕、32位采样/RR计数、首样本初始化、窗口回移饱和到0、空拍阈值更新与事件脉冲清零均按实际RTL。复位初始阈值表达式使用32位逻辑右移，覆盖信号初值小于噪声时的语义。不是浮点滤波基准，不模拟AXI/FIFO，不评估临床准确率。

新增 tests/tb_ecg_reference.sv 导出实际 RTL 的15个输出/状态字段；tests/check_ecg_reference.py 生成确定性时钟输入、运行Vivado XSIM、逐周期逐字段比较，并用人工预期检查smoke波形的16个事件。运行六组：默认smoke波形11722周期、360Hz随机2403、500Hz随机2403、窗口/不应期最小且初始估计0的1162、12位能量回绕2403、32位噪声高于信号复位分支822。共20915周期、每周期15字段一致，日志 PASS ECG_REFERENCE_ALL_CASES。没有 force 检测事件或修改 RTL；这不是全参数/全状态形式证明。

对照证据在 tmp/reference_check_20261014_01/report.json 与各案例目录，过程日志 tmp/reference_check_20261014_01.log，输入 vectors.txt/input.csv、rtl_trace.csv、python/trace.csv 与comparison.csv保留。独立 CLI 运行默认smoke输入至 tmp/reference_cli_20261014_01，事件16个，trace/events哈希与对照运行一致，覆盖命令行读写路径。全部输出在tmp，没有连接板卡、重建硬件或改发布版本。

README新增模型入口，移除“整数参考模型尚未实现”的过时描述，同时加粗smoke未上板。在现有下载教程第21节说明CSV格式、逐时钟/逐样本区别、运行和验证命令以及结果边界；没有新增重复Markdown。正式代码在项目目录。后续真实标注ECG回放、浮点滤波基准和准确率仍待完成；板子取回后先跑现有smoke，不跳过PS→AXI实测。Git仍暂停。

最终复核：对照报告中的4个源码哈希与当前文件一致，smoke产物与latest镜像未改，smoke boardExecution仍为NOT_EXECUTED。教程命令使用python -B，模型导入产生的本次字节码缓存可恢复移动到tmp/reference_python_cache，未删除文件。CLI与完整对照均退出码0。

### 2026-10-15：MIT-BIH 100号记录默认整数模型失败基线

用户授权先用100号真实标注记录评估现有参考模型，并再次强调smoke尚未上板。本轮只做离线回放，未修改RTL、参考检测器、PS配置、发布镜像或操作Git；smoke_board_test明确为NOT_TESTED。环境为本机Python3.14及已安装matplotlib，无新增安装。

先读当前AGENTS/myself、模型完整源码、检测器RTL与最近记录；按官方WFDB信号/标注格式新增scripts/evaluate_mitdb_100.py和tests/test_mitdb_100.py。下载官方100.hea/100.dat/100.atr与SHA256SUMS.txt到tmp/mitdb_100_20261015_01/raw。首次受限网络WinError10013，申请受控网络权限后下载完成，未绕过自动审批拒绝。三个原始数据文件与官方SHA256清单匹配；212解码的双通道首值、650000点及头文件校验和均通过；标注N2239/A33/V1及节律标签1条与官方组成一致。第一次交互式测试夹具把返回的双通道嵌套列表误写为单列表，修正夹具后通过；未因此修改解码实现。正式3组测试覆盖212符号边界、AUX/SKIP/附加字段和一对一匹配，全部通过。

MLII输入ADC减1024，比例1、范围[-543,287]，360Hz，不滤波/重采样/调参。默认模型120ms窗口43点、不应期200ms72点、初始噪声4096/信号16384。每样本后插入一个valid=0空拍；整个1805.556秒计分，不排除启动段。固定±54点/150ms有序一对一匹配，不移动检测位置。首次baseline输出得到检出0，故进一步独立按差分逐点重算窗口和，全部650000点与模型一致；复核版baseline_verified仍检出0。参考2273、TP0/FN2273/FP0、灵敏度0%、F1=0；阳性预测值、位置/RR误差无定义，不能因FP0称精度100%。

确认机制：积分能量全程最大1002，阈值全程最小4129、最大7168；signal_level全程停在16384，末尾noise_level553。RTL只在检测事件时更新信号估计；无事件时16384的四分之一使阈值存在约4096的下限，输入无法上穿。属于本次幅值单位与默认初始化不匹配的失败基线，不是数据损坏，也不构成其他输入比例/参数均失败的证明。后续应设计明确的输入幅值约定与启动期校准，并跨记录评估；本轮未擅自修复算法或通过标注调参。

证据：tmp/mitdb_100_20261015_01/baseline_verified/summary.json含配置、诊断统计和源码/数据SHA256；input.csv、reference_beats.csv、events.csv、matches.csv、missed.csv、extra.csv保留完整输入与计分清单；comparison.png已打开检查，前10秒及中段漏检示例清楚显示阈值高于积分能量。首次baseline目录保留未覆盖删除。README与原下载教程第22节同步实际失败结论及复现命令，不新增重复说明文档。没有上板、写Flash或确认断电启动；smoke仍须拿回板后实测。

### 2026-10-15：幅值映射及无标注初始化重跑100号

用户授权先改幅值和阈值初始化再评估，再次要求保留smoke未上板状态。本轮采用离线预处理与Config显式初值，不改变逐周期参考检测器或RTL，避免把尚未移植的校准宣称为板上已具备。新增software/reference/ecg_input.py，修改scripts/evaluate_mitdb_100.py及tests/test_mitdb_100.py；原脚本/测试备份tmp/backup/mitdb_calibration_20261015_01。原记录、默认失败报告及发布文件保留。

设计选择：幅值固定4096整数单位/mV，按头文件gain200、baseline1024换算，对称舍入至16位饱和；不用整条记录幅度最大值归一化，不用专家标注选增益。启动2秒720点的完整43点窗口能量，共677个，排序取floor((n-1)*0.5/0.9)索引为噪声/信号，最低1及噪声+1。本次初值1561/12475、阈值4289。先缓存2秒再估计并重置回放，因此起始2秒存在等待，并额外报告2秒后的指标。该方案不代表静默/强噪声启动可靠，后续需跨记录检查。

环境Python3.14与已有matplotlib，无安装。首次calibrated_01得到106事件、TP44/FN2229/FP62；随后仅精确化分位索引方法文字和增加诊断统计，calibrated_verified重跑同一结果，未调整参数追分。全记录2273参考、灵敏度1.9358%、阳性预测值41.5094%、F1=3.6990%；2秒后2270参考，TP41/FN2229/FP62，灵敏度1.8062%。匹配事件位置MAE94.0025ms，RR MAE3.1746ms只覆盖28个连续匹配区间，不能当整体准确性。输入范围[-11121,5878]，无饱和；独立窗口和全点一致。

波形已打开检查：前10秒有检测，中段约913秒阈值低于背景积分能量。全记录能量最大20522、阈值最低853，末尾signal933/noise827，640535/650000点能量不低于阈值；零检出的启动障碍已解除，但持续阈值下降导致后续绝大部分心搏无法重新上穿。源码在上穿时而不是能量峰值更新信号估计，是下一步需要核查的机制；本轮不扩大到峰值逻辑修改，不宣称临床或硬件验证通过。

证据在tmp/mitdb_100_20261015_01/calibrated_verified/及同名.log，五组测试日志calibration_tests.log；calibrated_01和全部历史基线保留。baseline_regression重跑默认输入及参数仍0事件，检查旧流程无改变。README及下载教程第23节记录方法、指标和等待边界。smoke_board_test=NOT_TESTED；没有操作Git、写Flash或更新latest，硬件仍待实测。

### 2026-10-15：持续阈值与候选峰的软件阶段完成

用户要求不要逐步反复询问，直接完成当前步骤并告知测试是否合格。依据此前阈值衰减观察，本轮新增software/reference/ecg_peak_reference.py和tests/test_ecg_peak_reference.py，扩展评估工具profile=peak。没有替换旧ecg_reference.py或RTL，保留旧逐周期语义；新文件明确是未移植的软件算法原型，旧模型一致性测试不替新模型背书。

设计取舍：沿用固定单位及前2秒无标注校准；用局部峰而非第一次阈值上穿更新信号估计。候选峰固定21点确认期内择最大，不随新峰延长截止时间；原波形43点窗口内找相对局部中位数的最大绝对偏离位置，保留200ms不应期，支持负峰。噪声仅用未接受的非不应期局部峰更新。软件采用足够位宽的完整窗口和，拒绝不能容纳最坏窗口和的参数，不声称与旧RTL等价或已具备同样回绕/计数语义。

首次peak_01全记录TP2272/FN1/FP1；随后仅增加位宽输入范围拒绝、分类型/分时段/确认延迟统计及误检绘图，未按结果调整增益、初值、阈值比例、确认时间或不应期。最终peak_verified重复得到同一2273事件。灵敏度与阳性预测值99.956005%，F1相同；匹配位置MAE1.490366ms，连续匹配2270个RR区间MAE1.519824ms。校准后TP2269/FN1/FP1，99.955947%。N2238/2239、A33/33、V1/1匹配，不把检测位置统计说成分类准确率。

本阶段采用暂定单记录开发检查：Se/PPV≥99%、位置MAE≤10ms、连续匹配RR MAE≤15ms，全部达到；这是项目开发判断，非行业标准、临床验收或独立测试，100号已参与开发，跨记录泛化尚未验证。前五个完整5分钟段均无FP/FN，第六段FP1，末尾5.556秒FN1；不删除尾部来提高分数。

错误复核：FN649991距记录结束9点，缺少后续峰确认输入，未填充尾部或从分母剔除；FP583009（1619.469秒）在额外振荡段，画图保留，不按该点再特化修补。确认延迟22.222—122.222ms、均值84.2377ms，为输入采样位置到输出事件差，不含2秒初始化等待，也不是板上时延或CPU运行时测量。

9项单元测试通过：原5项读取/校准/匹配，新增4项涵盖5000点静默、16个正负交替脉冲位置/RR、空拍不推进/复位、不应期去重、样本越界。全记录650000点独立积分核对通过。结果/源码哈希、事件清单、逐类型/分时段、确认延迟、development_gate=PASS在tmp/mitdb_100_20261015_01/peak_verified/；过程log和测试log在同任务目录。图片已打开检查首段、尾部漏检与误检三个位置。peak_01原输出保留。

同步README、下载教程第24节；原基线与仅校准回归分别存peak_stage_baseline_regression、peak_stage_calibrated_regression，防止评估入口改变旧算法结果。smoke仍NOT_TESTED/NOT_EXECUTED，没有PS/RTL移植、硬件构建、写Flash、替换发布或Git操作。下一阶段需要独立记录评估及候选峰RTL实现/一致性验证，板子取回后仍先补原smoke实测。

### 2026-10-15：竞赛计划缺项、英文目录与开源交付准备

用户授权把未完成事项加入计划，并先完成当前能做的目录/规范修改，工程未完成的最终报告和实测材料暂不编造。本轮据指南3.3.3—3.3.5迁移22个正式文件：RTL到src/rtl，PS源码到src/ps/ecg_smoke，软件参考到src/reference，测试与仿真到sim，硬件Tcl到build，PS构建到board，数据评估到data。计划docs/计划.md移为report/project_plan.md，教程docs/如何下载.md移为board/download_guide.md。旧源码/脚本/测试空目录只在确认无文件后移除；原tmp/vivado/Vitis工作区和发布版本不搬动、不删除。已有smoke的ELF/bit/launch仍可按原工作区Run，源码迁移不代表新检测算法已在板上。

迁移前保存目标文件完整副本及路径/SHA256清单于tmp/backup/layout_20261015_01；执行辅助脚本tmp/migrate_layout_20261015.py，逐目标检查项目根边界、目标冲突和写前字节版本，保留历史lykzr、tmp日志与latest清单原文。正式引用更新到新布局；检查中发现字符串替换误把文档中的tmp/rtl_tests/改为tmp/rtl_sim/，已修正文档，并让AXI仿真脚本使用实际输出变量报告路径。未改设计逻辑，RTL两文件及PS main.c与迁移前哈希完全一致。

build/create_rtl_project.tcl增加可选新输出目录参数，以便从独立tmp路径验证；sim/run_rtl_tests.ps1取消本机固定安装路径默认值，VivadoBin改为必填，增加OutputDir并拒绝覆盖已有输出。其他共享脚本仍按脚本位置定位根。根build/现在是正式脚本，.gitignore显式放行该目录的Tcl/README，其他子工程build继续忽略；新增忽略本机.rigel_lopper。Git仍暂停，未运行Git或改索引，规则放行不代表已经共享。

添加标准MIT LICENSE，署名2026 ecg_edge contributors，仅对有权授权的自有代码/文档；third_party.md分开说明数据库、AMD BSP/FSBL/IP、原始手册、PDF指南和运行工具，未将第三方全部改授MIT。数据库和最终二进制组件完整许可核查、实际GitHub/Gitee公开仍是计划待办。未上传资料、改变远端或安装依赖。

计划第9节记录当前证据、布局对照、smoke/多记录/RTL/板上回放待办、同器件资源性能基线对比、完整实现流水线、干净环境复现、最终报告/真实大模型交互/技能复用验证与最终许可/发布核查。不是仅建立空目录：data提供带固定哈希验证的100号获取脚本和依赖版本，复制三个历史summary及一次迁移后summary；sim保留精选20915周期对照报告；skill/README提炼黄金参考、GUI cwd排错、串口验收三项经验并注明失败来源/验证效果/失效条件，明确未上板和未验证PYNQ。没有写最终设计报告、虚构性能表或伪造原始协作记录。

迁移验证环境Python3.14、matplotlib3.10.9、Vivado2026.1：9项Python测试通过，现有100号原始文件与官方SHA256核验通过，新布局回放仍TP2272/FN1/FP1，位置/RR误差与迁移前一致。data/download_mitdb_100.py本轮验证的是本地已存在文件校验分支；首次下载分支沿用标准urllib/固定哈希，未额外下载一份或声称该分支已重测。完整输入与图在tmp/layout_check_20261015_01/record_100_peak，摘要复制data/results/record_100_peak_layout.json；原始记录、缓存和旧失败报告保留。

首次受限环境中xelab在生成C编译阶段失败，Vivado启动报Access is denied；读取错误后申请受控工具执行权限，在全新tmp/layout_check_20261015_02目录重跑。六组20915周期/15字段一致通过，smoke真实合成样本FIFO仿真通过，AXI自检通过；从空目录创建领航者PS7/AXI BD、validate及wrapper/IP输出完成。未运行新的综合、实现或生成bitstream。日志为tmp/layout_reference_20261015_02.log、layout_smoke_20261015_02.log、layout_axi_20261015_02.log、layout_bd_console_20261015_02.log。首次失败输出保留，不用权限重跑掩盖其发生。

最终复核：正式Markdown相对链接无缺失、正式目录名无中文空格；源码新路径哈希与回放报告一致，releases/latest仍9文件，BOOT.BIN哈希保持4B902DB837F8BB326F81775B745F651011403655D677EF0893D550C425F21A38，全部发布文件未改写。docs/materials_review.md未修改，参考PDF未移动。smoke boardExecution仍NOT_EXECUTED，板上/掉电/新算法RTL均未补写为通过。目录整理及许可证添加不代表完整作品已完成或仓库已公开。

### 2026-10-15：按11月4日18点截止重排计划

用户要求写入已确认的2026-11-04 18:00北京时间截止，并优先安排必须完成项。只修改report/project_plan.md正文与本过程记录：页首突出截止，第8节改为当前推进顺序，第10节列赛程来源、P0/P1/P2、分阶段日期和延期风险处理。以10月15日为起点约20天，内部目标11月1日完成包、11月2—3日上传核查，11月4日留作异常补救，不默认延期。

P0为smoke与板上核心链路、独立记录/软件RTL/板上回放、同器件基本优化证据和可复现交付；P1扩展噪声/质量研究，P2暂缓AFE/ADC、人体采集、复杂分类、换框架及新界面。前文长期MVP若与本轮收缩冲突，以第10节当前范围为准，未做质量感知不能写作已实现创新。10月20日仍无法安排板卡时需主动协调，10月22日检查新RTL稳定性，10月28日起冻结功能；落后时允许缩小实际分工，但必须重新验证并准确报告，不用Hello World或离线结果替代板上ECG。

已读取保存后的计划并核查截止、内部目标、优先级、日期表及smoke边界；smoke仍尚未上板测试，未勾选任何实验完成项。没有运行硬件、修改算法、重建镜像或操作Git；本次为计划调整，无需重复功能测试。

### 2026-10-15：将根README恢复为项目入口

用户指出README变成验证流水账。本轮按项目介绍、组成、目录、软件/硬件快速开始、文档导航与许可重写根README；移除逐日构建记录、默认失败/调参指标、历史缓存路径、旧板迁移过程和本机会话Git状态。详细数据与失败历史已在data/results、下载教程和本记录保留，没有删除这些证据。保留一段简短开发状态，明确候选峰尚未移植RTL、smoke尚未上板，避免读者误认功能完成。

写前备份tmp/backup/readme_entry_20261015_01/README.md并核对写前版本；保存后检查全部Markdown目标存在及状态文字。未修改代码、计划、镜像或Git；本轮为文档调整，没有重跑功能测试。

### 2026-10-15：复核旧smoke运行步骤在目录迁移后是否有效

用户粘贴旧步骤要求核对及必要路径修正。实际tmp/ecg_smoke/vitis_workspace仍在，ecg_smoke/_ide/launch.json配置名ecg_smoke_app_hw_1、resetSystem/programDevice为true、核0且stopAtEntry=false。核对bit、ps7_init.tcl、FSBL和应用ELF均存在，正式src/ps/ecg_smoke/main.c与已编译工作区副本SHA256一致，ELF仍2E573BA9A9244CD4A9EF0F5CE80ECA8957E1B512594B9B9389FC616353285BF7，配置bit与latest相同。旧步骤可以继续用，无需修改启动文件或重建。

首次只读检查命令中PowerShell提前展开workspaceFolder占位符，导致路径替换断言失败；改用字符构造保留字面量后，实际配置文件路径核对全部通过，没有修改launch。更新board/download_guide.md第20节，补充迁移后仍有效、准确配置位置/名称及串口8N1无流控；旧聊天中的docs/如何下载.md链接应改为board/download_guide.md。未写Flash、未运行板卡或操作Git，smoke仍未上板测试。

### 2026-10-16：按最新报名目标、多人协作与工具要求对齐计划

用户要求综合最近所有要求更新现有计划。本轮只修改report/project_plan.md，并追加本记录。完整读取当前计划/规则/本机边界、源码目录及已有验证说明，原计划备份tmp/backup/plan_alignment_20261016_01/project_plan.md（SHA256 98543A393429F0B56C32099579E12F6AB85C3C260BDDC95E989FD6493A253E66）。未覆盖其他成员源码、未修改README或旧实验报告。

纠正原计划与新简介的冲突：不再把1D CNN分类当后续可选扩展，也不把仅QRS/RR数字回放等同整件作品完成。将滤波/工频抑制、轻量1D CNN、INT8、PL推理、最小实时显示及ARM/FPGA同模型比较列为明确目标/待办，当前训练权重、量化及PL核心均标未实现。AFE/ADC保留条件目标并要求10月18日前核查，不因时间紧自动删除报名承诺，不未经授权购买、修改报名或连接人体。信号质量研究、LSM、框架切换和界面美化继续让位于核心目标。

增加分类数据/心拍窗口/类别映射/权重与数值接口、受试者分组、宏平均F1与混淆矩阵、量化损失和端到端切拍评估要求。特别指出100号已参与开发且正常心搏占多数，不能独自训练/验证分类；QRS99.956%不能冒充CNN准确率。训练与推理实现路线/层数/类别数未擅自选定，先由负责人冻结规则与资源预算。

按10月16日起约19天重排，保留11月4日18点北京时间外部截止、11月1日内部完整包、11月2—3日上传核查；10月16—18日确定负责人/接口和可行性，19—22日检测/滤波、CNN/量化、PS/显示并行，23—27日集成与真实测量，28日起冻结功能。落后时须团队明确取舍和材料口径，ARM分类不能冒称FPGA CNN部署。smoke仍尚未上板测试，拿到板优先实测，不使用日期表或旧Hello World结果替代。

新增第11节工作包A算法/数据/训练、B PL/验证、C PS/板上/显示，以及唯一集成人；姓名/人数未假设为已安排。每模块一位负责人、接口先冻结、黄金向量/权重/输入统一、每日小批集成、独立工作区与真实交接；Git持续暂停，计划更新不授权提交推送。

新增第12节：默认沿用XSim与Vitis裸机，ModelSim/Questa仅在队友需要且版本/许可/测试兼容时作为可选入口；核对AMD官方UG900支持列表和UG1144镜像说明。B盘约38.66GB下载缓存只记录为PetaLinux2020.2资料定位，不解压/安装、不混用2026.1；当前smoke原工作区不变。保留README为项目入口，细节不再回填根README。

保存后核查12个编号章节顺序、日期/截止、27项未完成清单、目标关键字及本地Markdown链接，并检查原“分类后续”“最低仅QRS”冲突条款已撤换。未勾选实验通过项，未执行新功能测试、安装、下载、构建、写Flash或Git操作；本次为计划和范围更新，不声称已完成CNN、人体采集或板上smoke。

### 2026-10-16：冻结QRS多记录评估与因果滤波参考

任务：按用户授权先推进离线算法/仿真，不分派多人、不做板上操作和CNN训练。保留100号为开发记录，在运行前固定101、103、105、108、119、200六条新记录，四配置raw/bandpass/notch/bandpass_notch；协议及原候选峰、幅值、初始化哈希保存在data/multi_record_protocol.json。未根据结果换记录、导联或调参数。

环境：本机Windows，C:/Python314/python.exe（Python3.14）、matplotlib3.10.9；无scipy/wfdb，未安装依赖。PhysioNet1.0.0下载先遇WinError10013沙箱网络限制，获工具权限后从官方HTTPS获取；起初逐条下载较慢，中止该下载进程后改为最多4个并行记录请求，已有文件仅校验不覆盖。最终7条记录的21个文件均通过官方SHA256；212两通道解码首值、长度、WFDB校验和通过。原始文件在tmp/multi_record_20261016_01/raw/，约14MB。

实现：新增src/reference/ecg_filter_reference.py，按W3C双二阶数学公式独立实现0.5Hz二阶高通+40Hz二阶低通（每级Q=1/√2）、60Hz陷波Q30及串联。逐样本因果浮点状态，转置直接II型，末级对称舍入/饱和；不使用双向滤波或事后相位平移。无标注前2秒校准，各配置缓存并重放；整个记录计分，不删启动/结尾，不补尾部未来样本。采样率360Hz，幅值4096单位/mV，±54点一对一匹配。MIT-BIH存在60Hz及部分记录30Hz相关成分，当前陷波不代表解决所有噪声；50Hz仅做合成配置检查。

新增data/download_mitdb_records.py、data/evaluate_mitdb_records.py与sim/test_ecg_filter_reference.py、sim/test_mitdb_records.py。后两项分别覆盖独立直接I型方程对照、稳定性/频响/流式状态/复位/饱和/合成正弦，以及导联顺序/文件损坏拒绝/计分边界。连同原9项，共15项检查通过，日志tmp/multi_record_20261016_01/unit_tests.log。新入口先复现100号raw TP2272/FN1/FP1，位置MAE1.4903658ms、RR MAE1.5198238ms，未破坏原结果。

实验结果：7记录×4配置共28次完整回放完成，evaluation.log及evaluation/下CSV/JSON/图片保留。新增六记录共3900000点、约3小时、12872个标注心搏。raw合并TP12499/FN373/FP2798，Se97.102%、PPV81.709%、F1 88.743%，仅1/6记录满足暂定门槛；bandpass为12381/491/2806、Se96.186%、PPV81.524%；notch为12473/399/2782、Se96.900%、PPV81.763%；串联为12351/521/2902、Se95.952%、PPV80.974%。所有幅值/滤波饱和计数为0。不能把100号开发高分或滤波单测通过写成跨记录通过。

失败定位：108 raw TP1431/FN332/FP2146，FP中1284个在最近标注之前150–350ms；图中主负峰前的正向突起有触发，带通后还漏主负峰。119带通FP从19增至336，排除前2秒仍334；约12.625秒宽负波额外触发，不能用整体平移解释。原因目前是候选峰/不应期/宽度和滤波后定位适配假设，未改算法验证因果。补充辅助脚本inspect_errors.py、error_diagnostics.json、108/119_interior_errors.png放同级tmp。按完整300秒块计算最差片段；JSON的worst_block也可能是最后5.556秒短尾块，报告已区分。

正式证据：data/results/multi_record_20261016.json与evaluation/summary.json字节/哈希一致（06C6C85FA891D295036FA595708E8718B2BBD1E41E55C99C26937076F0EF77CC），不包含原始波形。报告report/offline_qrs_evaluation.md；同步data/README.md、data/results/README.md、third_party.md和report/project_plan.md，根README不塞验证日志。编辑前副本在tmp/backup/offline_20261016_01/，写入前复核目标未并发变化。

结论与下一步：当前泛化未达门槛，不把带通组合默认接入正式链路。先用失败片段建立开发用例，研究重复触发和宽波定位，再安排新的未触碰记录评估；若本轮六条参与后续调参，就降为开发/验证集合。定点/RTL、分级ECG注噪、CNN数据划分/训练与实物验证均未完成。smoke仍NOT_TESTED/未上板；未修改RTL、PS、releases/latest或工具工程，未写Flash、运行Git或安装软件。

完成后复核：tmp/multi_record_20261016_01/artifact_checks.json记录28行统计、12872参考心搏、时间块/类别计数、源文件及协议哈希、精选摘要复制、Markdown本地链接、原smoke源码及BOOT.BIN不变等检查通过。用本轮备份对照四份已有说明/计划的实际差异，并检查新增源码语法和本次文本尾随空格；没有运行Git diff。该核查不改变上述尚未上板与算法未合格的结论。

### 2026-10-16第二轮：v2重复触发改进及新四记录检查

目标与授权：用户“可以，下一轮”，继续离线软件改进108/119失败，保留旧冻结基线，不做板上操作、CNN训练或多人分派。先读当前AGENTS/myself、源代码、首轮协议和报告；Git持续暂停，Computer Use禁用。原七条（100+101/103/105/108/119/200）全部转为开发验证用途；事先选106/109/111/203为新检查记录，不能交叉调参。复用官方获取脚本，在工具网络权限下下载新四条约8MB并校验SHA256；开发期间不查看新记录波形/标注/指标。

方法依据与实现：查阅Pan和Tompkins1985原论文的方法相关段落，参考窄带、斜率平方和近邻斜率判别思路；本库实现有不同滤波器/采样率/窗口/定位/恢复规则，不是完整原算法，不使用论文准确率充当本库结果。新增src/reference/ecg_qrs_v2.py、data/evaluate_qrs_v2.py、data/qrs_v2_protocol.json、sim/test_ecg_qrs_v2.py。旧src/reference/ecg_peak_reference.py、ecg_reference.py、ecg_input.py及首轮协议保持原字节/哈希。

v2使用360Hz、4096单位/mV输入；检测特征分支5–20Hz浮点IIR→相邻差分平方→80ms滑动和→局部峰后80ms有界确认，原波形有限窗口定位。200ms不应期不变，360ms内用0.5斜率比抑制弱近邻宽波；不能把检测窄带直接当作CNN/显示波形。前2秒无标注估计噪声/信号，缓存再重放全记录；全段±54点匹配，不平移、不删启动/末尾、不补未来样本。全部仍是浮点软件候选，未声明定点位宽或RTL一致。

开发尝试保存在tmp/qrs_v2_20261016_01/：trial_01阈值1/4，7记录TP15041/FN104/FP332，108误检2146→276、119 19→1，但108不合格；trial_02只抬高阈值至1/2，TP14360/FN785/FP33，其中119漏349拍，说明不能只追求少报，放弃。trial_03改为1/3并加入连续停检阈值释放，TP15042/FN103/FP204，F1较高，但新增合成幅值突降检查发现长期隔拍检出，不能作为最终版。

恢复逻辑：最近8个RR中位数作时长依据，超过1.66倍RR时逐级降低信噪差阈值，最低1/8；重获后重建信号水平，避免旧高阈值使后续心搏继续隔拍丢失，不回填历史事件。首次补丁把was_released放到了错误分支，出现UnboundLocalError，7项新单测中3项报错，trial_04回放也在100号v2开始时失败；已移到接受候选的正确分支。失败源码快照和trial_04.log保留，没有覆盖成成功日志。修正后新目录trial_04_fixed完成，TP15065/FN80/FP321，Se99.472%、PPV97.914%，5/7条达暂定门槛；选择满足恢复功能检查的版本，并非挑F1最高的trial包装成功。

最终开发逐例：108为v1 TP1431/FN332/FP2146→v2 1707/56/274，仍未合格；119为1987/0/19→1983/4/1，新增4个漏检也保留；200为2573/28/395→2594/7/2；100保持TP2272/FN1，FP1→0。105仍FP39，未通过PPV门槛。新7项检查覆盖极性/RR、valid空拍/复位、前导及宽后波、固定启动前缀、独立能量求和、240次/分合成脉冲、幅值降至30%后恢复连续检出、末尾不补样本；连同原15项，共22项通过，unit_tests.log保留。合成用例不代替真实心搏验证。

冻结：北京时间20:04:09（UTC12:04:09.688002）保存候选完整参数与8项实现哈希到data/qrs_v2_protocol.json，协议SHA256 3824DA09F3A8489991E62FD0413DD6E8C65BB9380D1E7143827A1DB5767F1B5A，算法SHA256 A56CD4DBD0F3FEC6CF0BDF13F23A246E6577E4E52C3A5D86B5926F11D1E62C63。之后才执行新四记录一次对照，evaluation入口先核对冻结哈希，不匹配即停止。新检查之后没有修改源码/参数或再按成绩调参。

新四条共2600000点、约2小时、9663心搏，全部输入饱和计数0。v1→v2：TP9598→9391、FN65→272、FP642→23，Se99.327%→97.185%、PPV93.730%→99.756%，位置MAE15.796→3.554ms，连续匹配RR MAE17.077→4.027ms；通过记录0/4→2/4（109、111）。106 v2为1892/135/10，203为2851/129/13，不能因误检少就宣称合格。

类别证据：新四条V标注1003个，v1匹配995、v2仅789；106漏128/520个V，203漏81/444个V。106近邻斜率拒绝0次、203为3次，不能把全部漏检归咎于这个规则。窄带/平方能量、单一信号阈值、不同形态幅值适配是待核验原因。下一步应研究宽/低能量QRS辅助特征、双阈值/受控回搜并重视逐类召回；目前不再用新四条调参，也不把v2移植为正式替代。若未来使用这些新记录开发，需要另留未触碰记录检查。

交付与边界：同一report/offline_qrs_evaluation.md追加第二轮，更新data/README.md、data/results/README.md、report/project_plan.md、third_party.md，根README不加入验证日志。精选开发与新检查摘要分别是data/results/qrs_v2_development_20261016.json（A91A9B198158A01515A6829DA1406A9AE7E39070E232F7B1BCD99417BAAFFD94）、qrs_v2_evaluation_20261016.json（473DF4B8DBB2E663911F77CD48E9A1F0AB79DF954A3699EA9C1049EDA3916E0C），均从原summary.json原样复制，不含原始波形。完整事件/匹配/漏检/误检CSV与对照图在trial_04_fixed和evaluation子目录，各trial也保存源码快照。既有说明/计划/本日志的修改前副本在tmp/backup/qrs_v2_20261016_01/。Python3.14、matplotlib3.10.9，无新增安装；smoke仍未上板，未改RTL/PS/bit/XSA/ELF/发布包，未写Flash或执行Git。

收尾核查：artifact_checks.json确认22行对照、52610个事件的范围/单调性/不应期/RR及计数一致，匹配容差、类别/时间块统计、两份摘要复制、冻结源文件和配置、Markdown本地链接、源码语法均通过。另用未冻结协议和不存在的raw路径作负向检查：入口先拒绝冻结缺失，未创建输出或读取数据。BOOT.BIN及原smoke C源码哈希保持不变；这仍不是上板测试。人工查看106失败对照图，保留其启动错误和V漏检证据，不再据新检查调参。

### 2026-10-16第三轮：成熟算法对照、GQRS流式复用与v3失败

用户授权继续改进至满意，并同意先用成熟算法对照。曾暂停解释对照用途，后获用户继续指令；同时按专用接口查询账号额度，未使用重置。工程仍只做离线软件，不运行Git、不操作板卡。先读当前AGENTS/myself和冻结源文件/结果；旧v1/v2及其协议保持不变。

隔离环境：全局Python3.14没有WFDB/SciPy。项目tmp/qrs_benchmark_env使用system-site-packages隔离环境；ensurepip子进程首次失败，改用without-pip并使用继承的pip完成本地环境安装，没有修改全局Python。通过工具网络权限安装WFDB4.3.1及依赖，实测NumPy2.4.4、SciPy1.18.1、matplotlib3.10.9。日志tmp/qrs_v3_20261016_01/pip_install.log；data/requirements_qrs.txt固定WFDB版本，不冒充完整依赖锁。用户中断前已启动的公开数据下载保留，后续检查均在冻结后进行。

同输入对照：新增data/benchmark_qrs.py，仍按完整记录专家标注、±54点一对一、不平移/删启动或末尾、逐V类计分。XQRS输入为相同整数幅值除4096的mV，使用4.3.1默认参数和learn=True；源码使用全记录filtfilt，明确只作离线对照。11条旧开发记录上XQRS TP24536/FN272/FP332，Se98.904%、PPV98.665%、V2184/2332=93.654%，并不是默认正确答案。GQRS按相同4096单位/mV给库，TP24766/FN42/FP152，Se99.831%、PPV99.390%、V2323/2332=99.614%，但QRS定位点到标注R峰的MAE约34.284ms。首次GQRS元数据引用processing.GQRS失败（该类未从包入口导出），改为定位gqrs_detect所在模块，新目录gqrs_default_fixed保留成功结果，失败gqrs_default.log不覆盖。

复用：逐段读WFDB4.3.1的GQRS初始化、平滑/检测滤波与决策循环。build/extract_gqrs_core.py按固定AST结构派生src/third_party/gqrs_core.py，保留MIT版权和全文wfdb_license.txt、gqrs_provenance.json（上游URL/模块/方法/派生哈希）。不是声称自行原创该核心。改动为每样本前yield，删除EOF补样与CLEANUP，每50ms检查已成熟峰而不只等新峰，有界64节点扫描，清除仅用于绘图的诊断列表。已向tmp/core_regenerated路径再生成，三个文件逐字节一致。

src/reference/ecg_qrs_v3.py提供push接口，只在GQRS滤波所需样本全部已输入后恢复；raw_at/at拒绝未来和过旧读取。固定4096原波形槽、4096斜率槽、2×1024滤波槽、64峰槽；不做全记录学习，不尾部补样。QRS内部峰附近原波形极值定位；双相近幅值峰优先选接近内部滤波峰者，不按标注拟合整体偏移。中心±80ms平均斜率低于外侧80–240ms背景时拒绝输出，该段参考心搏仍计分。最大确认等待按收到样本到输出位置计算，不当板上耗时。

开发迭代都在tmp/qrs_v3_20261016_01：stream_01为200ms（FP620），stream_02为280ms（FP146但203 V召回97.748%），stream_03为240ms/较宽定位（V99.786%、FP225）。stream_04尝试核心换算为200单位/mV以改善每拍±1的阈值适配，FP降至76但V仅98.756%；stream_05抬阈值1.25仍V98.714%，放弃内部200单位。离线quality_analysis只用开发数据比较中心/背景斜率，选中心平均斜率必须不低于背景的比例1.0，避免更高比例伤害V。stream_06恢复4096核心单位、240ms、质量检查，V99.914%、FP161；stream_07阈值1.5，最终开发TP24757/FN51/FP109，Se99.794%、PPV99.562%、V2328/2332=99.828%，10/11条达逐记录门槛，105强噪声仍FP60未通过。

测试和冻结：29项检查通过（原22项加v3七项），覆盖直流/零输入、极性、RR、240次/分脉冲、valid/复位、前缀与改变未来尾部不影响既有输出、禁止未来访问、长运行固定容量、无EOF补样、内部幅值换算、选定阈值与零能量候选拒绝。北京时间20:39:29.081694冻结data/qrs_v3_protocol.json，SHA256为5B2D590DF45998C10168EF246D23D62B0B6ED0774853B537588575C4FC0AB22E；固定15项实现/配置来源及WFDB qrs.py模块SHA。新8条114/118/202/208/213/219/221/228在开发前选定，冻结后只运行一次。final_development重跑v1/v2/XQRS/GQRS/v3确认同源；201因与202同受试者未作为新记录。

v3新8条共19133心搏：v1 TP19085/FN48/FP487，v2 17845/1288/16，XQRS 18839/294/20，GQRS 19111/22/73，v3 19106/27/332。v3 Se99.859%、PPV98.292%、V2109/2112=99.858%、位置MAE3.957ms、RR MAE4.506ms，只5/8逐记录通过；汇总PPV也没过预先99%里程碑，不能宣称成功。219单条FP284，图tmp/qrs_v3_20261016_01/219_errors.png显示真主峰后宽负波额外输出。208位置MAE12.358ms和228精度也保留失败。

因此继续v4，v3及15项冻结来源不再修改；把已看19条转为开发集，新预留23条写入data/qrs_v4_protocol.json，排除起搏记录102/104/107/217、与202同受试者的201，以及VF区间计分合同未定义的207。这是42条无起搏QRS范围的选择，不冒充完整48条或CNN划分。v4拟在输出侧加入近邻宽波检查，并保留双相/高幅值/高斜率救援，必须重新验证V召回；尚未据此标记测试通过。smoke仍未上板，旧PS/RTL/发布包无改动。

### 2026-10-16第四轮：有界流式候选的宽后波抑制与冻结检查

目标：在不牺牲低幅度/宽QRS召回的前提下处理v3的219额外触发，并用预留的新23条验证；当前用户允许继续离线修改，仍不做CNN、多人任务或板上操作。环境沿用Windows/Python3.14、tmp/qrs_benchmark_env隔离环境（WFDB4.3.1、NumPy2.4.4、SciPy1.18.1、matplotlib3.10.9），Git保持暂停。原19条全部用于开发，不再包装成独立测试。

新增src/reference/ecg_qrs_v4.py，继承冻结v3，输出侧在400ms近邻比较候选形态。先用中心区域中位数估基线，development_01结果TP43853/FN88/FP417，219仍FP264。诊断tmp/qrs_v4_20261016_01/shape_diagnostic.json表明宽负波把中位数拉低，正/负偏差比例看起来像双相波而触发救援。改用外侧80–150ms估基线后，development_02将219 FP降至1，但203低幅度真V也被拒绝，V召回仅96.847%；这是不能接受的取舍，不只看总FP。

增加低幅尖波合成检查后发现绝对斜率随幅度下降，无法单独代表宽度，最终改为斜率/幅度的归一化比较；双相比例≥0.25或相对前拍幅值≥0.75可救援。新规则拒绝输出时恢复last_position，但不撤销GQRS内部峰与自适应状态。development_03最终TP43863/FN78/FP159，Se99.822%、PPV99.639%、V4437/4444=99.842%，位置MAE3.565ms、RR MAE4.287ms，15/19逐记录通过；105/228的PPV、208定位/RR、219 V63/64仍失败。219 FP从v3的284降至3。

测试：sim/test_ecg_qrs_v4.py五项覆盖弱宽后波两种极性、小幅尖波/双相和高幅宽波救援、240次/分、valid/复位/前缀因果性、错误参数与EOF不补样；全sim目录34项检查通过，日志unit_tests_all.log。最初运行test_ecg*.py仅选到27项，随后补跑test_*.py确认完整34项，没有把27项误记成全套。三份派生核心/来源/许可证重新生成至core_regenerated，与正式文件字节一致；错误协议试验确认实现哈希变化会在读数据/创建输出前拒绝。

北京时间20:54:12.217835（12:54:12 UTC）冻结data/qrs_v4_protocol.json，完整ShapeConfig与18项源码/依赖清单哈希、上游qrs.py哈希都固定；协议SHA256=fd8ed1a1c081c896be484f0f1f89e21255a38bad9a6f51646b0c23ebd47d27d7。data/benchmark_qrs_v4.py为独立入口，保留原benchmark_qrs.py/v3协议/源码及其失败结果。新23条ID在修改前已写入协议，冻结后一次运行v3/v4/XQRS/GQRS，完成后不再修改v4。

新23条共52969个参考心搏：v3 TP52892/FN77/FP134；v4 TP52892/FN77/FP51，Se99.855%、PPV99.904%、V2143/2156=99.397%、位置MAE2.620ms、连续匹配RR MAE1.980ms，达到事先规定的五项汇总离线门槛。XQRS 52812/157/12，GQRS52921/48/227；v4不是所有指标最优。v4逐记录20/23通过，117位置MAE14.523ms，205 V70/71=98.592%，210 V185/194=95.361%，三条继续记录失败。117图中双相波定位在不同极值属于后续定位语义/误差分析线索，本轮不据此修改冻结版。210图保留漏检真V，不删标注或片段。

等待限制：多数事件收到R峰后约0.44秒才输出；116最长回搜补报4.086秒。这是输入样本确认等待，不是Python执行耗时、FPGA延迟或低延迟证明。下一阶段须固定心拍缓存、等待上限及在线/补报语义，然后做定点/C参考与RTL对照；不继续在新23条上调参。分级噪声、起搏/VF范围仍未验证；CNN数据划分需另定。当前可接受为限定范围的离线参考里程碑，不能说整套系统合格。

证据保存：tmp/qrs_v3_20261016_01/final_development/、evaluation/，tmp/qrs_v4_20261016_01/development_01/02/03/、evaluation/及各日志。新增data/plot_qrs_benchmark.py只读保存的CSV出固定前10秒/首个内部错误图，219_development.png、117_evaluation.png、210_evaluation.png均已打开核查。四份精选summary原字节复制到data/results/qrs_v3_development_20261016.json、qrs_v3_evaluation_20261016.json、qrs_v4_development_20261016.json、qrs_v4_evaluation_20261016.json；正式报告写report/offline_qrs_evaluation.md，更新report/project_plan.md、data/README.md、data/results/README.md、third_party.md，root README和materials_review.md未改。

独立复核脚本tmp/qrs_v4_20261016_01/audit.py和audit.json检查：v2/v3/v4冻结8/15/18项哈希；55/40/19/92行结果的CSV数量、匹配±54点范围、逐类/时间块合计、RR与事件/不应期、汇总重算；全部通过，流式stale_events均0。smoke main.c和releases/latest/BOOT.BIN与原哈希一致。修改前文档快照在tmp/backup/qrs_v34_20261016_01/，保留前几轮失败与原始资料，无删除/Flash写入/Git操作。**smoke仍未上板（NOT_TESTED），未改RTL/PS/bitstream或发布镜像，未训练CNN，也未验证真实AFE/ADC输入。**

### 2026-10-16：按用户要求归档历史算法版本

用户要求先不训练ECG分类模型，先规范文件，将上一轮历史版本放tmp。本次移动23个历史文件到tmp/history/qrs_20261016/，包括v1/v2/v3候选、旧单记录/各轮计分与下载入口、协议、专属测试和旧摘要。额外复制29个匹配依赖/整理前文档/当前结果快照，共52项记录在归档manifest.json中；所有原字节SHA256核对通过，未删除原实验、数据或历史证据。保留当前v4与两份v4正式摘要；摘要仍含当时历史方法的对照行，不篡改成新路径/新结果。Git持续暂停，未执行索引、提交或其他Git操作。

依赖处理：v4原先继承ecg_qrs_v3.py，计分入口又导入v1/v2与旧脚本的公共函数，直接移动会断导入。因此将v3实际运行核心原样拆为src/reference/gqrs_stream.py，v4只改导入；212解码/标注/匹配/读取/统计的原函数迁入data/ecg_dataset.py，相关计算AST逐项相同。活动入口data/benchmark_qrs_v4.py只保留v4/xqrs/gqrs，历史对照入口保存在归档，避免运行当前版本仍依赖旧版本。旧RTL逐周期模型及输入/滤波参考保留，不修改算法/参数。

冻结边界：归档保留原v2/v3/v4协议全部8/15/18项依赖哈希且验证一致。正式v4协议标明layout_migration、原协议SHA及原冻结时间，并记录新布局清单时间，不冒充原冻结协议。当前已查看数据的重跑只是路径迁移复现，不是新独立评估。所有旧摘要保持字节不变，以归档根解析其旧实现路径；旧实验tmp目录不搬动、不清理。

检查中先发现write_text改变公共核心换行，使字节一致断言失败；确认读取文本一致后改为原字节复制，再更新新布局清单，未改计算。当前23项测试通过，旧版本专属11项随历史移入归档；另从归档运行原完整34项仍全部通过。100/219/210三条完整650000点回放的事件列表和全部指标与整理前完全一致；正式计分入口用112已查看记录复现，events/positions/matches/missed/extra五份CSV逐字节一致。检查脚本、日志和verification.json均在归档目录，正式代码语法/当前文档链接检查通过。

文档整理：data/README.md和results/README.md仅保留当前入口/结果说明；report/offline_qrs_evaluation.md保留当前方法与结果，逐轮历史报告在归档；root README、sim/README、board/download_guide.md中的旧运行命令修正，项目计划补充归档位置。根实验记录历史段落不改写，docs/materials_review.md未动。发布BOOT.BIN与smoke main.c哈希未变；未训练CNN、未操作板卡/Flash，**smoke仍未上板测试**。本地tmp忽略不等于远端共享，交接历史需单独提供归档。

### 2026-10-16：日志统一到docs与全42条准确性复现

用户明确要求README以后只写工程说明，实验/调试/验证日志统一放docs，拆分后再测准确性。本次以该最新要求替代旧根lykzr.md约定，更新AGENTS.md第5/6节，后续本机实验记录改为docs/records/lykzr.md；保留其历史正文和原有忽略约定。board/download_guide.md移到docs/download_guide.md；report/offline_qrs_evaluation.md移到docs/records/offline_qrs_evaluation.md；发布validation.md移到docs/records/hello_world_validation.md。当前源码/仿真/发布README只保留用途、依赖、接口、运行/构建和文档导航；原README正文及其验证经过保存在docs/records/readme_history.md，计划中的详细既有实验成绩迁到project_status_snapshot.md。报告素材入口为docs/README.md。

写入前快照与SHA清单保存在tmp/backup/docs_records_20261016/，活动文件移动前核对当前内容和目标冲突。迁移初检发现Windows文本写入改变换行，验证摘要的字节一致断言失败；从本次原始快照恢复其原字节到新位置，对其他迁移文本以原文重算链接、直接写UTF-8字节，修正表格/列表换行而不改变历史结论。发布artifacts.json只更新README哈希和验证文档路径/哈希，原二进制文件条目、历史源码哈希、版本及实际验收状态均不改写。修正活动文档/本机说明中的教程和日志链接；docs/materials_review.md未修改，Git未操作。

拆分完成后重跑当前v4全部42条完整记录，使用原配置、原MLII/360Hz/4096单位及原匹配规则；开发19条与原评估23条分别运行。开发TP43863/FN78/FP159，Se99.822%、PPV99.639%、V99.842%，15/19通过；原评估TP52892/FN77/FP51，Se99.855%、PPV99.904%、V99.397%，位置MAE2.620ms、连续匹配RR MAE1.980ms，20/23通过。所有原记录角色保持不变，这次是已查看数据复现，不是新独立测试。

验证脚本tmp/qrs_recheck_20261016/verify.py确认：42条全部row字段和两组aggregate一致；每条events/positions/matches/missed/extra CSV及summary.json，共252份文件与整理前逐字节一致。当前23项软件检查通过，11项当前冻结实现哈希不变，活动文档链接及发布清单校验通过。117定位、205/210的V召回失败仍保留，不因文件整理或汇总通过抹去。详细结论和复现命令在docs/records/qrs_recheck_20261016.md；软件测试、开发和评估三份本次原始文本日志也位于docs/records/，CSV/JSON派生输出留tmp/qrs_recheck_20261016，未覆盖旧精选结果。

本次没有训练CNN、修改RTL/PS、安装依赖、操作板卡或Flash；发布二进制未变，**smoke仍未上板测试**。旧工具工作区和tmp历史不批量搬动，新需归档的文本日志按照本次用户要求统一进入docs/records/，README不再承载实验日志。


### 2026-10-16：按确认清单补全并重整AGENTS

用户确认将上一条27项回顾中除第7、16、24项外的要求补入工程规则，并规范结构。本次逐项检查24项覆盖，不新增被排除三项的具体本机会话状态或工作安排；原有通用授权和并发文件保护条款保留，不将“不新增”解释为擅自删除原约束。

AGENTS.md重整为：1上下文/授权/沟通，2项目目标/竞赛/优先级，3板卡/资料，4工程修改/工具，5算法/数据/训练/验证，6目录/历史，7README/文档/过程，8构建/下载/发布，9DeepSeek专项，10本机入口。补齐完整CNN/INT8/FPGA目标、截止和交付要求、数据划分及指标、准确性复测、教程/GUI工作目录、README与docs日志分工和解释术语等缺项。临时任务、具体成绩和本机配置不混入永久共用规则；myself.md仅补用户提供的B盘Downloads位置及使用前核查说明。

写前备份、差异和24项对应表位于tmp/backup/agents_rules_20261016/，coverage.json逐项对应原编号与新章节；verification.json记录检查结果。验证一级章节1—10及DeepSeek子节9.1—9.3连续，DeepSeek原文除编号/共用章节范围外不变，编码/链接检查通过，正文不新增被排除的具体状态。统一AGENTS换行为LF；当前算法11项冻结哈希不变，未修改源码或重复运行算法实验。本次只改规则/本机资料入口并追加本条过程记录，未执行Git操作。


### 2026-10-17：制作供其他电脑运行的 smoke 工程包

用户要求把 smoke 拷给另一台电脑测试。核对正式 main.c 与原工作区副本/ELF哈希，采用同一组合的bit、XSA和ps7_init，不拷带本机绝对路径的完整旧工作区。新增board/package_ecg_smoke.py、board/smoke_handoff模板和sim/check_smoke_handoff.py；包内提供预编译XSDB运行与本机重新创建Vitis GUI工作区两条入口，串口使用接收方实际COM、115200 8N1无流控，每次复位系统并重新配置PL。

最终候选tmp/ecg_smoke_kit_20261017_04.zip，459862字节，SHA256为7279d3dc8e25caa63fb9de2226f8a16ea08ed21df8318ed963cd97ca35ff7f65。ZIP/15项文件哈希、XSA内嵌bit、启动配置与离线替身调用顺序检查通过；重新从独立包路径构建平台/应用成功，导入源及PS初始化一致。新旧ELF仅GNU build-id20字节与调试信息差异，可分配节归一化build-id后相同；未把重建二进制当旧ELF哈希相同。

失败保留：2026.1的XSCT入口已禁用，改XSDB；Vitis批处理截断带空格绝对脚本参数，改相对调用，但工作区本身也不接受空格，入口明确提前检查。批处理可能报错仍返回0，增加构建产物/JTAG完成标记判断，替身验证无标记即拒绝。受限环境启动未继续、objcopy系统DLL重定位、Tcl替身source作用域问题及build-id比较初次不一致的排查过程，见docs/records/smoke_handoff_20261017.md与关联日志；失败包和工作区保留tmp。未连接板卡、写Flash、运行Git/Computer Use、安装依赖或替换latest。

更新docs/smoke_handoff.md、docs/README.md、下载教程和计划的交接入口。文档备份在tmp/backup/smoke_handoff_20261017_01。全库文档核查仍有未修改docs/HDMI.md的#L181锚点报错，本轮文档链接通过；根README、资料索引、latest及11项QRS冻结哈希不变。接收方工具/版本兼容及板上执行仍未验收，最终需完整BEGIN到PASS ECG_SMOKE failures=0且无FAIL日志；smoke依然未上板测试。

原先授权的CNN患者交叉验证训练未取消。交接期间发现原会话训练进程已结束但未完成（旧日志止于residual_verified第1折第6轮，原因未确认），保留tmp/cnn_patient_cv_v8_20261017_01全部产物，按相同冻结协议另启tmp/cnn_patient_cv_v8_20261017_02，日志docs/records/cnn_cv_training_20261017_02.log；当前尚在运行，不写成12组已完成或新模型合格，不读取保留的独立测试患者。

### 2026-10-17：更正为Git交接并接收smoke板上通过证据

用户明确指出要通过Git交接，上一轮ZIP交接误解需求。本轮改为克隆仓库后从官方固定原始文件直接生成开发缓存，无本机tmp/父缓存/ZIP/预训练权重依赖。新增data/prepare_cnn_git.py、cnn_git_v1_protocol.json、requirements_cnn_data.txt以及sim/check_training_checkout.py、test_cnn_git.py；ZIP打包器移至本地tmp历史，不再作为正式入口，已有ZIP不删除。更新训练交接说明、data说明、docs导航和计划；根README和资料索引仍受保护，未改写。

新协议为已评估v8 residual_verified的Git复现入口，保留26名开发患者三折、42条MIT开发记录、窗口/标签/训练采样和既有网络，只运行一个已选候选，不冒充新成绩。逐文件冻结61条INCART和42条MIT的309个原始文件SHA，与官方清单核对；既有下载校验通过。本机用现有原始文件完整重建143916开发拍、30842 MIT辅助拍，每字段张量指纹与原候选输入一致，开发NPZ字节哈希仍为f17c9345155b8f501a8d40ae367da013ea9c807a00ee9b1e6d9e84d67673d214；MIT子集字符串存储宽度不同导致NPZ哈希另立，值/顺序/标签/浮点严格一致，未改旧缓存。

用原三折残差权重在新缓存重放全部143916验证预测，一致；未重新训练、未读取独立6人测试。3项Git入口单元检查通过，原CV检查Torch环境3通过/1缺WFDB跳过；仅复制18个必要源文件到无tmp的另一目录，标准Python源码完整性/依赖检查通过。网络下载分支只在现有文件上完成全量SHA校验，未重新下载全库、未在第二台电脑安装运行；直接依赖固定数据环境NumPy2.4.4/SciPy1.18.1/WFDB4.3.1，训练环境既有CPU Torch不变。数据准备/下载检查/权重重放原始日志在docs/records/cnn_git_*，检查JSON在tmp/git_handoff_clean_check_20261017_02.json、tmp/cnn_git_input_replay_20261017.json。

读取Git状态发现旧索引已有很多新增/修改/迁移，未重置、暂存、提交或推送其他人的改动。发现全局lykzr.md和*.log规则忽略正式记录；.gitignore改为仅忽略根个人lykzr.md，并放行docs/records下过程记录和.log，tmp仍忽略。必要训练文件及返回UART不再被Git忽略。当前操作是交接文件准备及只读Git核查，不把本地状态称已共享；提交和推送需要明确解除之前暂停并确认范围。

收到用户smoke返回ZIP，原manifest15个载荷（另加manifest共16原文件）全部长度/SHA匹配，当前main.c SHA也匹配。保留用户原报告、UART、JTAG提示及原manifest至docs/records/smoke_board_20261017，不提取覆盖工作区源码/镜像。UART包含全部预期行、顺序一致、无FAIL，PASS ECG_SMOKE failures=0；比对最初因正常Synthetic samples提示多一行失败，后只允许这条已知说明行，所有事件/FIFO数值仍严格核验，原日志不修改。ZIP SHA d2af841f98201043c06d9d3e875507099fe35b21f3ddb788050b08cd7a42525e，UART SHA 268d65ed0fcb2b7d7a0fed2464a6fe97dc98ccf977fd8f8d8c0f10f6e57b13ff。

根据用户实际板上报告及原UART，当前smoke改记为PS→AXI→原检测器→FIFO合成自检通过（领航者V2、JTAG-HS1、2026.1、COM3/115200）；本会话只复核证据未重新操作实物。更新计划对应勾选及当前教程，详细证据docs/records/smoke_board_validation_20261017.md。没有把通过外推到ADS1292R实采、软件候选峰RTL、CNN/INT8/PL推理或QSPI掉电启动；JTAG掉电需重下载。旧记录/冻结训练元数据中的NOT_TESTED保留为当时快照，不再代表当前smoke状态。

文档检查仍仅4处HDMI.md缺失链接（其他工作已有内容，未恢复）；保护README/资料索引/latest及11项QRS哈希通过，scoped git diff --check无问题。没有安装、Computer Use、板卡/Flash操作或发布。四分类仍未合格，独立测试保留，后续模型训练由队友负责。

### 2026-10-17：smoke替换latest、旧版归档与串口辅助功能合并

用户授权本地更新release：归档Hello World、latest换成这次板上跑通的smoke，相关新功能合并，并再次提醒更新gitignore；明确不提交推送。先读规则、当前源码/发布清单和原始板上报告，核对返回ZIP与本地源文件，不把附件说明当其他操作授权。旧版releases/latest全部8文件原字节移至releases/history/20261013-hello-world-qspi-v1，目标不存在才移动，前后SHA256一致。新版本20261017-ecg-smoke-jtag-v1以hardware/prebuilt/board/src相对层级交付，manifest供脚本校验、artifacts记录原包来源/源码/证据与验收；主程序、ELF、bit/XSA及初始化五项与用户通过包相同。没有BOOT.BIN/FSBL/hello_world或QSPI启动声明。

返回包main.c和原JTAG启动脚本与正式文件一致，唯一新辅助工具capture_uart.ps1已合并正式board/smoke_handoff及latest；改为显式指定端口和日志，拒绝覆盖、CheckOnly无串口/文件操作、FAIL/超时报错并保留输出，兼容实际返回CR行尾。原返回脚本字节副本留tmp/backup/smoke_release_20261017。新辅助脚本只做离线检查，不把修改后采集脚本称已实物复跑。当前两份RTL与旧硬件源SHA一致；构建Tcl找到SHA匹配历史备份逐行比较，仅两处rtl路径改为src/rtl，无新增逻辑/PS参数。本次不重新综合、实现、下载或烧Flash。

同步build_ecg_smoke默认XSA、打包器产物来源至最新hardware/prebuilt，候选打包加入capture脚本，不再依赖本机tmp工作区；更新发布README、下载/跨电脑教程、docs入口和计划，旧QSPI步骤不再错误指向新的latest。根README与资料索引保持原样。gitignore按18项当前发布文件的明确嵌套清单放行，history、workspace及非清单bin/脚本继续忽略，check-ignore --no-index逐项通过；没有改索引、提交、推送或清理。

发布离线核验通过：16载荷加manifest/artifacts共18文件，全部字节/哈希、正式源码同步、XSA内嵌bit、ARM ELF、启动配置和原UART关键行一致；旧归档8文件仍一致。PowerShell run_smoke CheckOnly、新capture CheckOnly和AMD XSDB Tcl --check-only均通过，未连接板卡；新增采集脚本语法通过，已存在哨兵日志测试拒绝覆盖且原字节不变。正式打包器重新生成tmp/ecg_smoke_release_repack_20261017.zip（462006字节，SHA a337e001318ea15297b40d1ca6330b99c00304a02c8e225da2062f51f046e39e），原ZIP检查器通过；重新打的候选包仍NOT_TESTED，不自动继承新的板上验收。代码语法和scoped diff --check通过。

实际发布过程与限制见docs/records/smoke_release_20261017.md，离线最终检查docs/records/smoke_release_checks_20261017.log及tmp/smoke_release_final_verification_20261017.json，归档映射/旧哈希tmp/smoke_release_update_20261017.json。全库48 Markdown/328链接复查仅4处既有HDMI.md缺失，发布新增链接及QRS11项冻结SHA/根受保护文件/旧归档原字节检查通过；未恢复他人文档，未称全库无错误。当前smoke合成自检已据用户报告通过，JTAG掉电需重下载，ADS1292R实采/CNN/INT8/PL/新候选QRS RTL和QSPI启动仍分开未验。旧Hello World的QSPI证据保留，不混成smoke成绩。

### 2026-10-17：收紧日志跟踪与暂停训练

用户要求先解决238项更改中原始日志过多的问题，同时询问smoke之后做什么。核查当前238项均暂存，docs/records共120项，其中97份.log；97份全为新增暂存，HEAD中无这些日志。本次授权下只对日志索引和.gitignore作定向处理：取消91份下载/安装/逐轮训练/重复检查等原始日志的暂存/跟踪，本地文件不移动不删除；6份精选日志仍跟踪：smoke UART、JTAG启动、发布检查、QRS开发/评估复核、当前CNN CV权重复核。正式md报告、源码和发布文件继续保留。

.gitignore移除两条全量日志放行，改为逐文件6项例外；同步本次规则至索引，避免随后提交旧放行规则。操作前备份.gitignore、Git索引及各路径/哈希至tmp/backup/log_tracking_20261017。逐项比较索引，除91日志移除和.gitignore对应更新外，其余索引条目不变；97个日志文件SHA256全部不变。没有全局reset/stash/restore、没有清理文件、提交或推送。改动条目从238降至147，剩余仍是多个此前阶段累计，不能统称一次smoke更新。

docs导航补充精选日志跟踪约定：其他原始日志留本地，历史链接可能仅作者机器可用，不为补链接重新全量放行。计划记录用户当前暂停模型训练，下一阶段做PC串口协议解析/离线演示和波形事件记录，再做PS受控连续送样与板上联调；采样率/滤波来源/序号与命令能力不预先伪定。本次不写新协议/显示程序，不动当前已通过smoke镜像，也不跑模型训练。

### 2026-10-17：UART第1步计划与武断表述审查

用户指定先完成协议关键定义、先写计划，不明确标记并检查是否存在武断；本轮仅修改report/project_plan.md、docs/uart_protocol.md与已有导航/本记录。完整读取原草案及当前计划/寄存器，核对RTL计数、FIFO实现、PS smoke及构建Tcl；不启动模型、PC/PS程序、仿真/板卡或发布。原文副本及目标哈希保留tmp/backup/uart_stage1_plan_20261017。

计划第13节拆为协议、PC离线、独立PS流式、板上连续验收四个工作包，逐项列进入条件/交付/验收/当前状态，顶部注明本轮只做第1步文档、训练暂停。第1步文档审查已补齐，最小线协议仍有待决，不把草案冒充最终冻结。

协议改为事实/建议/待确认三类：源码事实是样本0基、事件32位首1，rpos为积分窗口回移后的候选位置，0x20计事件丢弃不是丢样，当前无运行时SET_RATE/软件复位/滤波波形读出。UART统一0基、能力位0—6、filt=NA、分类?/-1等明确为待冻结建议；不能拿原始值/积分能量当滤波，也不能拿数字4096映射当真实ADC已标定。U01—U07列真实采样/滤波来源/会话同步/末批和统计/命令/波特率校验/记录策略，并写明最迟决定节点。

纠正未确认默认真实360Hz、DMA必选、缩批保证节拍、事件固定1Hz、连接必收H、PS协议默认不改RTL却保证滤波输出、重编协议必改smoke、CRC确定留v2、手写PNG与PC必为HDMI备份等口径。HDMI.md当前缺失，移除协议对缺失页的链接，不恢复他人文件或据缺页决定分工。示例无省略报文且注明离线示意，未知分类不写虚构N/90。

带宽按8对满宽int16、uint32最大10位序号、LF/无校验计算125字节/批（CRLF126），360Hz为5625字节/秒、500Hz为7812.5，占115200/8N1理论11520字节/秒的48.83%/67.82%；仅规划估算，事件/状态/日志/校验和峰值另计，不当无丢样实测。未知真采样参数没有强行选择，10分钟仅候选验收时长。

本轮文档检查：完整示例字段数/NA/分类未知值、RR/心率换算、125/126字节最坏W帧及360/500估算通过；协议/计划锚点链接通过，仍仅docs/README中他人HDMI缺失链接，协议本轮已不依赖缺失页。第1步七组待决均可定位，根README/资料索引/.gitignore与Git索引哈希不变，未暂存/提交/推送；未启动PC/PS实现或模型。核验摘要tmp/uart_stage1_plan_verification_20261017.json。

### 2026-10-17：PC离线监视器初版

用户授权先将“未知采集硬件不阻塞PC开发”写入计划，再开始编写。读取当前规则、计划、协议和相关源码后，正式代码放src/pc，单元测试sim/test_pc_monitor.py，教程docs/pc_monitor.md；同步协议、目录说明和计划第13节。目标文档原字节及保护文件哈希保留tmp/backup/pc_monitor_20261017。没有新装依赖；现有Python3.14.7/Tk9.0.4可用，PySerial缺失，本轮只用标准库。

采用独立流解析/会话记录/界面三层。软件v1补H的session/source/detector、W实际批量n=1..8、T三类独立丢弃统计；旧未发布草案不静默猜测兼容。256字节行限、回绕/重复/倒退检测、未知单位/滤波/类别明确显示，事件按实际样本位置匹配。Tkinter演示与快速文件回放提供波形、事件、心率/RR及错误统计，SVG为补充；数学波形和指定事件不是QRS/CNN输出。初稿演示曾将无真实FIFO/UART队列的丢弃计数填0，检查后改为-1未知，保留早期tmp输出，不把旧文件当最终证据。

记录新目录排他创建，保存原字节、三个CSV、会话JSONL及摘要；默认数据总量64MiB，到限额停止，不覆盖/删除/轮转历史。原始块先写，限额中止可能CSV不完整，结束原因需一起检查；完全磁盘满时摘要也可能失败。显示缓存有界，完整记录另存。尚无实际串口输入、PC命令发送、PS流式或ADC驱动，不改板卡/RTL/smoke发布、不训练模型。

最终检查：14项测试通过（合法与拆包/坏行恢复、超长/非ASCII、无H/截断、重复及新会话、32位回绕/缺口/倒退、事件早到、未知值/能力、容量与非覆盖、CLI原文重放）。隐藏窗口自检通过：1084样本、1个波形图元和4个事件图元，Tk9.0.4；仅构建/绘图对象检查，不是人工操作验收。10.01秒数学演示接收3604样本、13事件、451个W、11个T，30993原始字节，坏帧/缺口为0；原始日志重放后raw/样本/事件/状态/会话五文件字节一致，不作为算法准确率或真实采样节拍成绩。最终证据tmp/pc_monitor_demo_20261017_02、tmp/pc_monitor_replay_20261017_02、tmp/pc_monitor_ui_check_20261017_02；摘要tmp/pc_monitor_verification_20261017.json。

根README、资料索引、gitignore、latest和Git索引哈希保持原样；未暂存/提交/推送。已有HDMI文档缺失不恢复。下一步先人工使用离线界面，再单独实现PS流式和串口适配/上板连续验收；真实fs/ADC位宽/增益/电压映射、滤波来源及延迟仍需实物核查。已通过的合成smoke与本次软件检查各自保留，不宣称ADS1292R实采或分类/INT8/PL已验证。
### 2026-10-17：按三类整合计划和修改日志

用户要求把全部未完成工作分为信息采集、项目主体、模型训练，并整合计划和修改日志，教程不管。本轮只重整report/project_plan.md、docs/records/lykzr.md和文档导航。计划用A/B/C编号集中列当前状态、优先级、接口与验收：采集交付连续数字样本；训练交付浮点/INT8整数参考；FPGA推理部署、PS/PC、滤波/QRS、自动切拍、整机验证与竞赛交付归主体。不将仅完成软件检查的PC或原smoke推成整机验收，训练暂停状态不变。

旧计划重复/过时的“smoke待上板”及“当前只做文档”等不再作为当前任务；历史正文没有回写。原日志整条分组并保持类内顺序，混合记录保留完整，分组映射和原字节备份在tmp/backup/three_category_plan_20261017_01。信息采集没有独立实采成功条目，明确留空缺口，不拿芯片讨论或USB供电记录冒充。专题实验报告、原始日志与教程原位保留，避免破坏证据/链接。

本轮仅文档结构检查与文件哈希对照，未重跑算法、模型或板卡；不改变原验收成绩。保留旧UART第13节锚点以兼容未修改的协议链接；核对三类任务和原日志无遗漏、保护文件与源码/教程/发布及Git索引未变，验证摘要tmp/three_category_plan_verification_20261017.json。没有提交或推送，也没有新增授权。

### 2026-10-17：明确项目主体的电脑通信与显示范围

用户指出分类概述没有突出电脑通信显示，本轮明确B08—B11含板端发送、PC串口接收/解析、原始/滤波波形、事件/心率/RR/分类显示、原文/CSV保存与连续联调。已有离线初版不等于真实串口已完成。与A07采集数据输出口分别交付，和模型C11/C13的整数参考/端到端检查关联更新。仅文档更正，不修改教程、接口源码或发布。

### 2026-10-17：三类计划拆成独立文档

用户确认计划书修改后，要求三块分别成文。本轮新增report/acquisition_plan.md、system_plan.md、model_training_plan.md，分别保留A类8项、B类16项、C类13阶段的任务/状态/验收及交接内容；project_plan.md改为总览、共同排期和入口，专题不再各自复制排期。原B02已迁A06，滤波和采集输出接口在采集专题，电脑通信/PC显示在主体专题，模型完整流程和训练暂停/失败边界保持。旧UART第13节锚点在总计划保留并指向主体专题，教程/接口规范不需要改动。修改日志仍按原三类维护，不搬动专题报告或原始验收证据。

同步docs/README.md导航，写前保存原字节和哈希至tmp/backup/split_plans_20261017_01。仅文档拆分，没有开发/模型/板卡验证或新成绩，未暂存提交推送；根README、资料索引、教程、源码、发布与Git索引保护。任务完整性、链接/锚点与保护哈希检查摘要tmp/split_plans_verification_20261017.json；既有HDMI缺页未恢复。

### 2026-10-17：增加计划完成勾选标记

用户要求以后每做完一项都打钩。本轮在三份专题的37项任务表增加“完成”列，☐代表未完成/进行中/暂停/待验，☑仅代表该项全部验收通过；完成时同步日期及证据，复验失败取消勾选并追加原因。总计划统一说明维护规则，不复制状态表。当前37项整体条件尚未全满足，保持☐，已有成果仍在状态列说明；主体计划用独立已勾选子项标出原检测器smoke验收和PC离线软件检查，不把后者当真实串口或整机验收。

仅更新四份计划和本记录，备份tmp/backup/plan_checkboxes_20261017_01。核对新增勾选列去除后37项原任务/状态/验收文字保持一致、两条已验收子项证据链接有效；教程、源码、发布、根README及Git索引未变。检查摘要tmp/plan_checkboxes_verification_20261017.json；没有新训练、模型/板卡测试或提交推送。

### 2026-10-17：简化计划文件名并分类文档导航

用户希望Markdown命名更朴实好找，并要求docs/README.md分类。本轮将三份新计划改为report/capture.md（采集）、report/system.md（主体）、report/model.md（模型），总计划project_plan.md和标准README/AGENTS入口保留；正式命名继续英文。只同步当前计划间和总计划/文档导航的链接，旧日志中的原文件名是当时事实，不批量替换。三类任务和完成勾选内容不变。

docs/README.md按信息采集/项目主体/模型训练分组，原先段落中重复的交接/发布入口收入相应分类；共有目标和三类日志在开头提供。既有HDMI缺页注明待补，不恢复文件。教程、历史专题报告、源码及发布均未改名/改内容。备份与重命名映射tmp/backup/simple_names_20261017_01，链接/任务内容/保护哈希检查tmp/simple_names_verification_20261017.json；未运行模型/板卡测试或Git提交推送。

### 2026-10-17：合并重复smoke文档入口与过程记录

用户同意合并重复的smoke说明。保留docs/smoke_handoff.md为自检/跨电脑统一入口，操作细节复用下载教程和latest；将原smoke_handoff_20261017.md与smoke_release_20261017.md按阶段合为后者，原正文仅调整标题层级，早期未上板明确为当时状态，失败/数值/来源不删改。板上通过证据smoke_board_validation_20261017.md及原始UART/报告保持原字节，避免破坏当前发布钉住的证据哈希。

旧交接记录原字节移至tmp/history/smoke_docs_20261017_01，其他目标原副本在tmp/backup/merge_smoke_docs_20261017_01。docs导航原4个分散smoke入口缩成1个，记录/交付通过统一入口访问；旧日志的原路径不回写，新归档映射随本记录保留。没有删工程/旧数据、改源码/教程主文档或修改release。检查合并正文完整、原字节归档、链接及当前smoke发布离线核验，摘要tmp/merge_smoke_docs_verification_20261017.json；没有实物复跑、Flash操作、训练或Git提交推送。

### 2026-10-17：详细核查Git交接、工程与算法验证依赖

用户确认需可直接打开的Vivado工程，并要求详细查看模型/算法验证等遗漏。本轮审查正式导入/默认协议、XPR引用、根ignore、旧权重/预测和验证入口；不操作Git索引/提交推送。旧tmp XPR仍引用迁移前rtl，故从既有配置在正式vivado/ecg_edge生成新文本工程，复制wrapper出.gen并只放行3文本文件；旧工程/历史不动。修正build忽略遗漏，放行extract_gqrs_core.py；从归档原字节补4份仍被正式代码引用的旧协议。没有改变RTL/PS参数或6项冻结训练/模型源文件。

已选residual_verified三折29原始文件1,229,443字节复制data/baseline，附来源清单与说明；新增check_baseline核验来源/身份/指标及可选权重重放，check_checkout与清单覆盖124项当前交接文件。首个干净副本软件测试因test_mitdb_records假定tmp存在失败，只补测试目录创建，在新02副本通过。数据环境61项51通过/10跳过，Torch环境51项39通过/12跳过；同机已有解释器，不假称接收电脑已安装。GQRS生成3文件逐字节复现；Vivado新路径无原缓存打开、引用及BD验证通过，IP恢复/解析警告保留；不综合/实现/bit/上板。

干净副本RTL首轮xelab生成C文件失败，临时目录仅在重试子进程内改为项目tmp后成功；六配置20,915周期×15字段一致，未证唯一根因，失败目录保留。模型143,916个已知开发心拍重放与原预测一致，平均折macro-F1=0.6413631469852122、合并OOF=0.6239157252749785，仍未合格；未训练、未读6人测试。smoke发布离线检查通过，原报告/UART与latest全字节不变。

同步build/data/sim/vivado工程说明、训练交接的精选日志口径、文档入口与计划子项勾选；C12/B12整体仍未完成。其他历史专用实验仍本地可恢复，未承诺全部旧实验Git复现；根规则核查不冒称实际索引或远端状态。完整发现/命令/限制见docs/records/checkout_20261017.md；备份tmp/backup/checkout_audit_20261017_01，最终摘要tmp/checkout_audit_verification_20261017.json。根README、资料索引、冻结源/协议、Git索引和当前发布保护；无安装、Computer Use或Flash操作。

### 2026-10-17：补齐跨模块输入、异常恢复与演示验收

用户同意把完整链路核查的七处缺项补进计划。本轮在capture1.4、system2.5、model3.6细化原A/B/C任务的验收条件，并在对应表格引用，没有新增编号或勾选未验项目。优先输入训练/实采一致、原始/滤波/事件切拍时轴、启动/缺口/恢复；另补实际时钟跨域/复位约束、CNN与PS事务接口、完整延迟/吞吐预算、最终JTAG或QSPI启动方式。无信号/削顶/接触异常按实际可监测条件说明，不臆定模块能力或疾病输出。

强调源丢样与PC显示缺口分别处理、不能无依据全链路重置；窗口/预处理变更另立实验版，实际状态字段需协议同步；DDR/DMA、异步FIFO、心跳停流和看门狗均未默认选定。QSPI仅计划确认/验收，未获烧写授权，不操作Flash。记录当前后窗约533ms只是协议等待预算，未当硬件实测，也不把所有流水等待机械相加。

仅修改三份计划及本记录，教程/接口规范、源码/模型/发布、根README及Git索引不动。备份tmp/backup/integration_plan_20261017_01；任务编号/完成状态、跨文档链接/锚点和保护哈希检查见tmp/integration_plan_verification_20261017.json。没有新训练、算法/板卡测试或提交推送；所有细化子项保持待验。

### 2026-10-18：修正外部协作控制与CNN诊断建议

用户授权修改docs/project_control_plan.md、docs/cnn_analysis_and_suggestions.md，保留有用建议、去掉无依据与冲突，不改原目标并同步日志。本轮改为引用正式总计划/采集/主体/模型专题的执行辅助：保留关键依赖、职责建议、接口与回归检查、已有输出诊断和风险升级；不另立排期或通过标准，不取消采集/滤波硬件化/CNN/INT8/PL，不将分工和前端条件写成未经核实的事实。

删除无来源的比赛得分/耗时/文献F1区间与固定loss/batch容量判据；删除自动降门槛、二分类或PS替代PL的行动指令。CNN独立6人继续封存，不以其结果决定是否继续，引用现有工程门槛和开发选型规则。核对代码后补明现有类别权重/患者截断/AdamW/Cosine衰减/batch256/早停已实施，历史微调/比例校正/背景失败需先复核，不默认没试过。不造日志曲线或标注错误根因，不以模型误判删改难例。

用现有check_checkout/check_training_checkout/check_baseline/check_smoke_release及build/share入口代替不存在脚本和缺参数命令；不实际执行。移除无证据的已发送勾选、修改根README等建议，会议/人员/范围变更由实际确认。两文档修订日为2026-10-18，绝对节点引用正式排期，避免今天/天数过期。

写前备份tmp/backup/review_docs_20261018_01，原文可恢复；仅上述两文档和本日志改变，三份计划/总览、根README、资料索引、代码/协议/基线、release、gitignore及Git索引哈希保护。链接/锚点、既有门槛和输入/资源数值一致性核对见tmp/review_docs_verification_20261018.json。本轮纯文档，不训练、不看独立测试、不安装、不发送消息、不操作板卡/Flash或Git提交推送；原失败和板上验收结论不变。

### 2026-10-18：项目主体接续与Windows串口只收适配

用户明确本会话负责项目主体并按计划继续。本轮先补B09串口接收：原PC演示/回放不能连接端口，新增src/pc/ecg_serial.py，依据微软通信句柄/DCB/超时资料使用标准库ctypes；GUI实际COM输入、115200/8N1/无流控、DTR/RTS禁用、每40ms最多4096字节立即返回读取，CLI同入口可限时接收。复用原行协议与CSV记录，不发送命令、清空缓冲、自动复位或重连；空读不作断连，没有H不猜会话/单位。错误停收、限额保留、半行不跨重连；摘要记录尝试配置/打开状态/收取字节/相对时刻/错误，不能冒充源丢样或采样时间。

新增sim/test_pc_serial.py，全部使用假驱动；原14项与新增14项共28项通过无跳过，包含底层结构/配置/有界原字节读取、句柄清理、打开/配置/读取/关闭失败、驱动错误、分块等价、无H、半行断连、限额、Ctrl+C、隐藏窗口连接停止重连。另加载真实kernel32签名但未打开COM；已有隐藏窗口自检1084合成样本/4事件通过，Python3.14.7/Tk9.0.4，未安装依赖。checkout126文件/49Python及smoke16payload检查通过；检查不等于真实串口或板上连续验收。

同步report/system.md及总览当前授权/状态，B09整项仍未勾选；仅勾选软件适配子项，后续B10独立PS流式程序/节拍/发送队列仍待实现。维护src/pc和sim说明、PC教程、UART状态、文档导航与交接必需清单。完整结果/限制见[PC串口记录](pc_serial_20261018.md)；慢磁盘/事件循环积压、实际驱动拔插/吞吐和人工使用待验，不承诺满负载无丢字节。

写前副本tmp/backup/pc_serial_20261018_01，范围和保护检查tmp/pc_serial_verification_20261018.json。原日志保留，模型训练与独立测试未启动，采集/模型目标和验收门槛未改；原smoke/RTL/发布/根README/资料索引与Git索引不动，无实物/Flash/Git/Computer Use操作。

### 2026-10-18：独立PS合成流与真实BSP构建

按用户继续项目主体和下一任务授权推进B10，新增src/ps/ecg_stream的硬件适配与可移植C核心、board/build_ecg_stream.py、C假外设及8项主机测试。现有360Hz硬件上按PS全局计时器排期，默认3603个合成脉冲/零样本；仅声明SYNTH、未知标定/滤波/分类。完整读FIFO队首并成功排队后弹出，原序号位置不改；8KiB有界字节队列、W预留1KiB给控制行，慢发送丢整批并按样本统计，超期不追赶、事件/控制排队失败停采，无普通printf交错。H名义每秒重发，不接命令、不自动重置；每次重新配置PL/新PC记录仍必要。

8项主机检查最终无跳过通过，真实stream.c由既有GCC以C11/O2/Wall/Wextra/Werror编译，假1000003Hz时钟/AXI/FIFO/UART输出经现有PC解析。正常3603样本/10事件/零发送丢弃；慢发送提交3603、丢971、接收2632，独立计数正确；另验3点末批、20点后采样超期停止、UART停滞、旧PL/错误配置拒绝、0序号/位置事件与非法合同。源值和排期有独立C断言；测试不执行QRS，不冒充真实硬件节拍或检测成绩。首次2条测试断言涉及重复H幂等计数、慢速参数未构成足够压力，改查原字节/施加真实压力，并明确末尾缺口须结合总量，不改PC规则。

Vitis本机服务回环连接受沙箱拒绝，客户端等端口未返回；获准沙箱外构建后真实BSP暴露xtime_l.h未导出，读取xiltimer.h及官方globaltimer_sleep_zynq.c改用当前接口。失败工作区归档部分被占用，Move-Item虽打印ARCHIVED但未完整完成；保留tmp/ecg_stream残留及tmp/history/ps_stream_20261018_failed_01，不强行移动。重建被已有目录保护拒绝后改新tmp/ecg_stream_retry_02/vitis_workspace，应用ELF编译链接成功，287124字节，SHA256 67ac7db9ab3fd68d646ae4524488940bf17e7159b88e8cfe35b1097cef926a96。源码副本/硬件组合与ELF清单核对；自有主机C无警告，BSP原厂FSBL比较及路径警告保留，不称零警告。

证据采集遇GCC系统TEMP权限错误，获准重试仍失败；只改子进程TMP/TEMP到项目独立目录，不改ACL。TemporaryDirectory自动清理另有拒绝访问，测试改为保留UUID输出目录/原日志，不强行清理。最终场景证据tmp/ps_stream_validation_20261018_03/results.json，8项unittest最终通过；失败目录保留。全过程与边界详见[PS流式记录](ps_stream_20261018.md)，操作见[使用说明](../ps_stream.md)。

同步主体/总计划、UART候选范围、导航、仿真说明与源码交接清单；仅勾选主机检查/ELF构建子项，B08/B10/B11整项仍待实物。写前副本tmp/backup/ps_stream_20261018_01，最终核验tmp/ps_stream_verification_20261018.json。未修改PC界面、根README、资料索引、原RTL、smoke及release；未开始模型训练/独立测试、未操作板卡/Flash/Computer Use或Git。下一步实际节拍、FIFO/W对齐、串口/PC连续联调，随后另验真实采集。

### 2026-10-18：PC监视器界面布局与状态提示整理

用户给出初始等待截图，指出信息堆叠、启动即显示“尚无合法H报文”等技术提示、空白图显示0.000→0.000、比例不统一、缩放/高DPI可能越界及运行状态难区分。本轮只改PC界面，不改协议、解析、记录、限额或串口读取；ecg_serial.py、ecg_uart.py字节未变。

原因核查：draw()用max(实际宽高, 900/330)作绘图尺寸，Canvas小于该值时网格/波形会画出可见区；说明文字固定wraplength=1050；info_text把H缺失提示放在启动时，stop后不区分历史。

修改：ecg_monitor.py重排为状态徽标+来源说明、离线/串口/记录三组操作、五个数值卡片、波形、“最近事件/诊断详情”分页和状态栏。状态分为未开始、合成演示中、日志回放中、串口等待、接收中/暂无新数据（2s无字节只提示，不判定断连）、已停止·历史数据、已停止·出错。空白图按状态给操作引导，不再显示坐标范围；“尚无H”只在串口已开时出现，并按是否收到字节分别说明。停止后卡片标“历史数据（已停止）”，坐标轴加“历史数据”。caps未声明CLASS时类别显示“未提供”，?显示“未知”，不显示N；演示时事件列为“标记位置（演示）”。协议/缺口/丢弃/解析错误/串口字节/记录目录移入诊断详情。绘图按Canvas实际尺寸和字体行高计算边距，图例/坐标文字按宽度换行，右侧事件号换边；ecg_monitor_core.plot_geometry只新增可选margins参数，默认值与原硬编码一致，SVG输出不变。Windows启动前声明DPI感知，边距/表格行高按DPI放大；窄窗口时“本次记录”组换行。start()先清空显示Monitor，打开失败不残留上次数值。

检查：本VM的Python3.10没有Tkinter，无法安装（apt无权限、pip代理403），未安装任何依赖。项目映射目录内TemporaryDirectory清理报IsADirectoryError（改前原代码同样28项中12项报错），因此把src/sim复制到VM本地/tmp执行。改前原代码28项通过（1跳过）；改后30项（新增2个隐藏窗口用例：串口非协议文本→等待→读错误态；演示/回放状态及300×180、760×260、1600×700下图元不越界）在无Tk环境27通过/3跳过；另用自写最小Tk替身执行界面逻辑30项全过、--ui-self-test通过（ui_scale1.5，1084样本，canvas_bbox在1000×360内）。替身只模拟控件/图元坐标，文字宽度为近似，不等于真实Tk渲染。10.01s演示3604样本/13事件/30993字节，回放后raw/samples/events/status/sessions/waveform.svg六文件逐字节一致。check_checkout.py在Linux因data/baseline/files.json反斜杠路径失败，与本轮无关，未修改。

未做：真实Tk/Windows下的人工视觉检查、150%等缩放下实际观感、真实串口和板端联调均未执行，隐藏窗口/替身检查不能代替。用户需在本机运行`& './tmp/qrs_benchmark_env/Scripts/python.exe' -B src/pc/ecg_monitor.py`及两个测试文件复核。B09整项不勾选。同步docs/pc_monitor.md界面/状态说明、sim/README.md测试范围。写前副本tmp/backup/pc_ui_20261018_01；根README、资料索引、release、计划及Git未动，无板卡/Flash/Computer Use操作。

### 2026-10-18：用户实际演示日志回放复核

用户给出本机初始/停止演示截图后，要求由本会话检查日志回放。本轮找到tmp/pc_monitor_logs中的20261018_221836_69bc3c4e（2256样本/8事件，与截图对应）及20261018_221822_377f2845（4944样本/17事件），分别以当前CLI的headless replay入口在新目录完整重放，退出码均为0。两组raw.log、samples.csv、events.csv、status.csv、sessions.jsonl各5文件逐字节一致；摘要的样本/事件/协议计数、元数据与错误字段一致。原记录结束原因stopped_by_user、回放为completed，输入方式也不同，故不要求summary.json整文件相同。

另用标准库CSV独立核对全部样本序号连续、事件号从1递增、演示位置144+288*i、首RR0/其余288、后续心率75.0，滤波/电压/分类置信均未伪造；两组均无波形/事件缺口、解析错误或关闭错误。原记录所有文件哈希前后不变，没有覆盖用户数据。输出与详细哈希在[verification.json](../../tmp/pc_user_replay_20261018_01/verification.json)。

环境为本机既有Python3.14.7，无新依赖。用户截图能确认当前初始与停止演示状态实际显示，不能据此确认所有缩放/状态栏或串口场景；本轮CLI回放未操作GUI，不替代GUI回放视觉、真实串口或板上连续联调。仅追加本日志，写前副本tmp/backup/pc_user_replay_20261018_01/lykzr.md；未改源码/计划/原记录/发布，不勾选B09整体，未操作Git/板卡/Flash。

### 2026-10-19：500Hz流式候选适配，传输方式另议

用户要求修改500/360Hz差异，第一条34/10字节传输先记下待讨论。澄清34字节来自通信协议DOCX，与main.c实际10字节不符，非TI芯片PDF冲突。当前独立合成流改为500Hz，统一PS节拍、H/T、心率换算与PL参数；5003点，60点积分窗、100点不应期。初始化读回配置不匹配则不送样，保留360Hz smoke/latest及旧构建，模型输入和真实AFE未改。

主机9项通过（含独立360Hz兼容），ADS解码14项与PC核心14项回归通过；500/360Hz真实RTL/FIFO仿真均通过。首次Windows bat参数等号传递失败，保留目录并改独立500Hz测试顶层后通过。新增独立硬件构建入口和更新Vitis路径；500Hz综合/实现/bit/XSA及匹配ELF均构建完成，ELF为286784字节，最终哈希核对通过。详细产物以[本轮记录](stream_500_20261019.md)为准，不用旧ELF冒充新版本。备份tmp/backup/stream_500_20261019_01，检查tmp/stream_500_checks_20261019。

PS流式程序仍未上板，B10/B11不勾选；真实DRDY、通道、标定、滤波及模型适配待验。传输结构未更改，接入路线/校验/序号留待讨论。无Git、训练、板卡或Flash操作，根README/资料索引/latest未改。

### 2026-10-19：固定电脑中转路线，输入与结果协议分离

用户确认ADS1292R→STM32→蓝牙→电脑→板载USB_UART→Zynq，Zynq经同一连接返结果。先更新总计划、采集/主体计划与协议：采集厂商10/34字节不混入电脑输入ECG-IN-1，Zynq结果仍为ECG-UART-1。新增独立电脑CLI中转和PS接收应用，保留smoke、500Hz合成回归和原Tk界面；不自动猜通道/边界/单位，不安装依赖或操作原件。

实际PS C核心与电脑中转完成离线双向闭环：新18项及原43项相关回归通过，覆盖5003点逐值回传/事件关联、模拟8ms四点蓝牙分包、CLI原码保存和控制/结果分流、CRC/乱序/重复/拥塞/超时/限额等；原监视器回放1003点/2事件五文件逐字节一致。AXI由原检测器软件参考模拟，串口为受控模型，不算RTL或实际外设联调。首轮适配器误用step接口导致ctypes回调异常，改为tick并增加异常立即失败检查；时钟回退原因覆盖也已修正。

最终Vitis ELF构建于tmp/ecg_bridge_final/vitis_workspace，294076字节；源/硬件/ELF清单与完整失败过程见[本轮记录](usb_bridge_20261019.md)，入口见[中转说明](../bridge.md)。仅勾选离线子项，B10/B11与真实流式程序仍未上板；蓝牙型号/实物帧/通道/标定、双连接GUI和持续负载均未验。模型训练暂停，根README/资料索引/latest/训练基线和合成流源码保留；Git未操作、无板卡/Flash动作。备份tmp/backup/usb_bridge_20261019_01，检查tmp/usb_bridge_validation_20261019。

### 2026-10-19：统一中转文件命名

用户要求类似功能使用相近命名，方便浏览。本轮将电脑协议/采集/双向串口模块统一为ecg_bridge_protocol/capture/serial；两份说明统一为docs/bridge.md与bridge_protocol.md，测试为test_ecg_bridge.py和ecg_bridge_host.c。同步当前导入、文档链接及交接清单；旧实验正文/临时工作区保留原命名，映射追加至[中转记录](usb_bridge_20261019.md)。板端组件、构建入口、线上协议和结果监视器不改名。

Windows项目独立Python环境及已有GCC运行更名后的18项中转测试全部通过，CLI帮助及checkout通过（155文件、60份Python、29项冻结模型基线）。根README/资料索引/latest/板端C及ELF共24项保护哈希不变；备份tmp/backup/bridge_names_20261019_01，检查tmp/bridge_names_verification_20261019.json。仅命名及引用维护，不新增准确率或硬件成绩；流式/中转仍未上板，未操作Git、训练、板卡或Flash。

## 三、模型训练

### 2026-10-16：CNN训练准备与现成模型调查

用户明确开始分类训练准备，随后要求多找现成且质量高的ECG模型。本次先检查现有环境和42条标签，新增data/profile_classification.py用于官方SHA校验、类别盘点和候选切拍边界统计，不安装PyTorch或启动训练。当前Python3.14.7环境没有torch/torchvision/sklearn；CIM硬件查询未成功，PATH没有nvidia-smi，GPU仍未知，不推断为一定无GPU。

候选N/S/V/F计数86947/2546/6601/801，另Q15；256点前96后160窗口完整数86909/2546/6600/800。N包含束支阻滞和逸搏，不能当作健康标签。代码仅借QRS协议确定已下载记录池，没有沿用QRS集合为CNN划分，也没有冻结四组任务或窗口。42条全部原始标注与WFDB rdann解析的位置/类型完全一致；盘点、独立对照JSON在tmp/cnn_prepare_20261016，原始文本日志在docs/records/cnn_data_audit_20261016.log。

通过论文作者/维护者的公开入口核对十条路线：CLEF、ECGFounder、ECG-FM、torch_ecg、Tiny MF-CNN论文、PTB-XL作者基准、Mousavi seq2seq、TenzinDhonyoe单心拍分类器及两个FPGA案例。详见docs/records/cnn_model_survey_20261016.md，区分官方权重、框架、论文结构和第三方复现，不把README成绩当本机验证。重要发现：CLEF-Small约448K参数、Zenodo checkpoint约5.5MB，但仓库已归档；ECGFounder单导联权重约370MB；Tiny MF-CNN体积小且做跨受试者研究，本轮未找到作者官方权重；同7020的SE案例是ECG5000二分类、24位定点和自报DSP210/220，不能套作本项目INT8多分类。另一ML605案例软件INT8与硬件16位Q8.8、类别口径也不同。

推荐优先核查现成小预训练模型的输入/许可/最小推理，并与任务匹配的小1D-CNN基线比较；尚未选最终模型、加载权重或划分CNN集合。训练前检查预训练数据与测试受试者重叠，通用表征需适配分类头，参数/模型文件大小不等于7020资源占用。完整代码、权重校验、算子/MAC/缓存预算及量化均未验证。

计划按最新授权调整为CNN选型/划分/训练优先，不再把QRS先移植RTL写成训练前置；计划修改前快照在tmp/cnn_prepare_20261016/project_plan_before.md。README只新增盘点工具使用命令，研究结果写docs/records。代码语法、文档链接及原QRS11项冻结哈希检查通过。未运行Git、安装训练软件、修改QRS/RTL/PS或发布镜像，smoke仍未上板。


### 2026-10-17：01:00续接文档维护与轻量CNN首版训练

用户要求先规范正式Markdown，根README.md不动，凌晨在本对话推进小型CNN并把CLEF-Small另存备选。上轮只写了整理脚本、未完成落盘；本轮重读AGENTS/myself/目标文件后执行，备份在tmp/backup/doc_maintenance_20261016。下载教程的历史成绩和排错迁入docs/records/bringup_history.md，保留原章节入口；修正旧board教程自指、结果链接、Flash类型与当前发布说明的不一致；计划和docs导航同步，AGENTS补随手维护及根README保护。保护文件和发布README/清单哈希未变；当前冻结QRS11项哈希未变。文档清单/链接证据见tmp/doc_maintenance_20261016/verification.json，维护范围见docs/records/doc_maintenance_20261016.md。

CLEF备选保存docs/model_candidates/clef_small.md。本机已有两套Python均无torch/TensorFlow，未安装依赖；为了先建立可复现基线，按Farag 2023固定模板MF-CNN思路独立实现NumPy版本，明确四个超类模板、三个因果RR、固定训练特征标准化等改编，非官方模型或完整可训练卷积。代码src/reference/ecg_mf_cnn.py、data/train_ecg_cnn.py，协议data/cnn_mf_v1_protocol.json，说明docs/cnn_baseline.md。参数844可训练/128固定卷积/8标准化，浮点MAC初算10320/拍，不代表硬件资源/延迟或INT8通过。

训练16条38236拍、验证4条8930拍、测试22条49675拍，201/202同人隔离；专家位置切拍且全42条已参与过QRS研究，不称全系统未见数据。seed20261017，Adam0.001/batch512，上限80轮，验证macro-F1选权重、耐心12；实际15轮，选第3轮。验证macro-F1为0.567899；测试总体准确率92.4429%，macro-F1仅0.423830，S召回0.8710%、F召回0，首版分类质量不合格。训练本身S召回8.14%、F为0，可能存在简化特征/模板不足等问题，尚无消融证明，不归咎单一原因。保留全部失败，不改测试阈值、划分、类别或删除困难记录，也不更新发布镜像。后续优先检查公开可训练卷积变体，已查看测试不得再冒充独立。

数值梯度、标量卷积对照、玩具数据学习、因果RR与同人隔离等6项检查通过，全部29项活动软件检查通过；独立循环重算保存预测的混淆矩阵/macro-F1及哈希/集合核对通过。权重、数据NPZ、逐轮日志、源快照和JSON在tmp/cnn_mf_v1_20261017_01，详细结果及原始文本日志在docs/records/cnn_mf_v1_20261017.md及关联log。没有Git、安装软件、Computer Use、多人分派或板卡/Flash操作；smoke仍未上板测试。


### 2026-10-17：连续18组可训练CNN实验，严格四分类仍未合格

用户要求一直尝试直至合格，实在不行明确告知；并明确允许仅项目独立环境安装CPU PyTorch及必要依赖。本次创建tmp/cnn_torch_env，确保临时/缓存在项目tmp；ensurepip默认临时目录权限失败和沙箱代理访问失败均留原日志，改项目TEMP并获工具联网权限后安装PyTorch2.14.1+cpu/NumPy2.5.2，没有改系统Python、驱动、ACL或代理。

预先固定本轮工程目标macro-F1≥0.85、各类F1≥0.70、N/S/V/F召回≥0.95/0.80/0.80/0.70、参数≤100000，注明是助手提出的原型目标，不是比赛/用户/临床要求，后续不降。新增可训练MF/残差结构及训练脚本；v2六配置均衡采样，v3四配置标准化RR/自然加权/去BN/增强，v4四配置长128点上下文，v5四配置针对验证较好的双通道MF继续自然加权/增强；18组共636轮。全部保持同一受试者角色和四类，无随机心拍跨人泄漏或删除F。每轮选权重/候选只看验证，之后旧测试回放均标已查看探索性证据。

训练已经能达到macro-F1约0.95，跨人验证/旧测试仍下降。按验证选的全局候选context_residual_both16_aug，训练0.952439、验证0.749199、旧测试0.530255，S/F召回分别33.642%/4.897%，accepted=false。未按别的候选测试较高分改选模型。训练S516中383来自209，F401中372来自208，验证F仅11拍，覆盖集中为已确认风险，但尚无证据证明唯一原因。18组比较和失败分析见docs/records/cnn_trainable_20261017.md；记录停止当前调参依据及需要新数据/建模/独立评估，不能把当前模型算合格或偷偷删F。

8项PyTorch检查通过，原环境29通过/8跳过且跳过项已在新环境实测通过；独立循环重算各轮混淆矩阵/macro-F1、权重/协议/运行源码快照及按验证选择结果均通过。相同8928个验证ID比较确认排序不变。上下文等待R后约533ms、额外15个N边界样本排除如实记录；各轮源快照保留64/128点兼容扩展前后版本。v3继承的augmentation文字标签瑕疵已披露，实际候选augment与源码决定行为，冻结原文不事后改。正式说明、数据README、计划、第三方来源及本机环境同步维护；根README/资料索引/发布包未改，不写README成绩。未运行Git或使用板卡/Flash、Computer Use、多Agent，smoke仍未上板。

### 2026-10-17：扩大S/F来源、冻结新患者测试，4候选81轮仍未合格

用户要求优先补S/F受试者数据并重新安排独立测试后训练。本次沿用已有CPU PyTorch2.14.1+cpu/NumPy2.5.2环境及WFDB4.3.1/SciPy1.18.1数据环境，没有新安装。先获取官方元数据/标注并核对患者映射与许可，再冻结v6：INCART75条/32名患者，20人训练、6人验证、6人测试；同人I文件不跨组。INCART带S/F患者19/14人，实际新增训练S/F患者11/8人。SVDB78条身份/导联位置不明，仅辅助训练，不称78人。旧MIT42条全部转本版已知开发训练，旧协议/成绩不改，201/202别名仍受控。

主站完整波形下载长时间无完成，Range诊断观察1MiB主站约50秒、官方归档约6秒；停止自己持有的下载会话后改有限Range分块/可恢复缓存，完整文件仍核对固定版本官方SHA256。CIM进程查询被系统拒绝，未改权限；使用已有会话中断。INCART/SVDB新波形886593600字节通过校验，所用导联首值/模和通过。首次跨采样率最大差检查在零边界失败，定位为滤波瞬态；分别核对主体差、全窗RMS、R位置，并验证360Hz与旧上下文一致。原因、失败和完整日志在扩库记录，不删失败历史。

v6使用128点/144Hz、约356ms前窗/533ms后窗、物理mV逐拍归一化、因果RR及训练独立标准化；训练上限按患者/类别限定，SVDB按记录作为采样单位而非患者。训练84727拍，N/S/V/F为46497/12064/25214/952，可确认S/F患者41/24人，分别较原训练11/8人扩大；验证31928拍，测试31835拍。v6残差/MF两候选共41轮，只按验证选残差，macro-F1为0.554281，S/F召回35.621%/3.125%，失败保留，新测试不评估。

补查欧洲ST-T90条元数据，F354/S1095，尚未训练；需单独处理同人映射与MLI/MLIII/胸导联。LTDB7条长程元数据有F2908，6条记录带F，但身份仍不明，约94%F来自两条；不能称新增6名F患者。发现原始gain0被WFDB解析代填200，本次另立v7明确用未标定ADC逐拍归一化（下限1ADC），不称恢复mV；只辅助训练。LTDB214072320字节波形（含310格式）官方SHA、首值/模和通过。预选训练拍按固定哈希与上限，RR仍更新全部标注拍，用401间隔有界历史并验证与全历史等价。v6验证/测试缓存逐字节复制至v7，身份角色不变。

v7训练99554拍，N/S/V/F为47897/13564/34478/3615；未知身份数据不计可确认患者数，仍为S41/F24。两候选40轮，验证选MF24（2532参数、198816Conv/Linear MAC仅算术预算），macro-F1为0.558534，S/F召回53.595%/21.875%，精确率仅11.824%/14.894%，F1为0.193739/0.177215，accepted=false。两轮4候选共81轮，按同一验证比较选v7 MF，未按旧测试挑模型，不把小差异当稳定收益。验证失败后保持新6人测试未用于模型评估，两输出目录无开封标志/测试预测；正式入口增加验证失败拒绝开封检查，v6旧运行快照与v7新快照均保留。

本轮49项软件检查分环境实测：数据环境38通过/11因无PyTorch跳过，独立PyTorch环境8个卷积/训练检查和3个测试保护检查通过；不把跳过说成单环境全过。独立循环重算两轮预测混淆矩阵、macro-F1、训练RR统计，核对协议/数据/权重/运行源快照以及相同验证/测试字节，均通过。14个变更文件语法/尾空白检查通过，文档链接和受保护文件/QRS冻结哈希检查通过，最终入口见扩库记录。源码/脚本和两协议在data，工程说明docs/cnn_expanded.md，实验docs/records/cnn_expansion_20261017.md，原始数据/缓存/失败模型/备份均tmp；计划与来源同步维护。

数据扩充完成不等于分类合格。下一阶段先按来源消融和开发患者分组验证，审查输入/RR与有效S/F覆盖，再决定新建模方案；不重复消耗保留测试、不删F/困难患者或降低门槛，不直接进入INT8/PL。未运行Git/Computer Use、多Agent、板卡/Flash或发布操作，根README、资料索引及原发布包未改；smoke仍未上板测试。

### 2026-10-17：记录心拍分类、节律与疾病判断的范围

用户要求保存近期关于ADS1292R、四分类覆盖和根据心拍提示疾病的讨论。新增docs/records/ecg_scope_20261017.md，引用PhysioNet底层标注、常用五组研究映射、TI官方资料及NIH诊断说明，区分事实、当前实现和候选后续方向。记录N/S/V/F属于限定单拍分组，N含束支传导阻滞等不等于健康，S不等于房颤、V不等于室速/室颤，F不是房颤；Q/起搏/未知不在当前训练输出，五组也不等于完整疾病分类。

心拍与连续ECG可以提供部分心律异常线索，具体疾病判断不能由单个分组直接推出。记录采集→检测/切拍→分类→连续节律/事件→异常提示的功能层次，节律种类/窗口/标注/验收及未知、低质量出口仍待定义，不把讨论当成功能已完成。原简介的采集、CNN、INT8、PL、显示及ARM/FPGA对比目标保留。ADS1292R作为采集候选，芯片能力与实际模块联调分别表述；500SPS仅讨论选项，未核对模块不记为前端已实现。

同步docs/README.md入口、docs/cnn_expanded.md解释及report/project_plan.md的范围/待办；本次为文档维护，未改变训练类别、源码、冻结协议或结果，未训练、未操作Git/板卡/Flash或安装依赖。写入前备份四个目标至tmp/backup/ecg_scope_20261017_01并核对字节，追加前确认本日志未发生并发变化。文档链接、冻结协议/运行源码与受保护文件检查见本次检查记录；未重跑无代码变更的软件训练。分类质量仍未合格，新6人测试未用于模型评估，smoke仍未上板测试。

### 2026-10-17：完成患者CV、来源对比及新时序CNN训练

用户要求继续模型训练。接续当前v8进程，完成4方案×3折共12次训练、336个epoch；原中断31轮保留，不并入完整轮数。新源码为data/prepare_cnn_cv.py、data/train_cnn_cv.py、src/reference/ecg_temporal_cnn.py及冻结data/cnn_patient_cv_v8_protocol.json；本轮补独立sim/verify_cnn_cv.py，更新sim/test_cnn_cv.py、工程说明/数据说明/来源和计划。训练期间未改运行中的模型/训练源码，也未改变冻结协议。

26名INCART已知开发患者三折9/9/8，143916拍，N/S/V/F=125997/1508/16250/161；原6名独立测试完全排除。128点/144Hz公共网格、仅历史RR、每折训练拟合RR标准化、自然构成验证、训练内部采样上限。来源对比为可确认身份MIT+INCART，与额外加入SVDB/LTDB未知身份辅助；结构对比为既有残差与两层Conv1D/16段时间池化/RR分支，自有实现无预训练权重。CPU4线程、batch256、AdamW、平方根类别权重及冻结早停；环境Python3.14.7/PyTorch2.14.1+cpu/NumPy2.5.2，未安装新依赖。

按预定三折平均macro-F1：residual_verified0.641363、residual_all0.575238、temporal_verified0.617226、temporal_all0.581724，全部accepted=false。所选残差的合并开发OOF macro-F1为0.623916，S精确率29.163%/召回86.870%/F1 0.436667，F精确率10.390%/召回44.720%/F1 0.168618；不能用准确率96.492%称合格，也不和旧v7不同验证池的0.5585直接比较提升。新小网络虽减至10468参数/119472Conv-Linear MAC，未提高总体质量，未称FPGA实测加速。

实际观察：加入辅助来源在这组配置下未改善；不能据组合对比单独归因SVDB或LTDB。MIT辅助800个F中734个来自两名患者，INCART开发池161个F来自11人且多数很少，覆盖局限保留；不能把拍数增加当泛化问题已解决。完整逐患者与混淆矩阵见docs/records/cnn_patient_cv_20261017.md及运行目录。后续需受控审查患者均衡/来源差异/表示或校准，不能继续相同轮次冒充解决，也不降门槛或删除困难类别。

独立检查器重建采样/患者分离/RR统计，复算每折/逐患者/合并指标与门槛，核对协议/数据/源码快照/权重哈希，并从12组权重重放575664个开发验证预测，全部一致。证据tmp/cnn_cv_verification_20261017.json及docs/records/cnn_cv_verification_20261017.log；复核通过表示失败结论可信，不表示模型合格。新4项软件检查在数据环境2通过/2跳过、Torch环境3通过/1跳过，互补覆盖4项；5份Python语法通过。首次中断前31轮与重跑除耗时外逐字段相同。准备缓存的NPZ懒读取核对曾因重复解压缓慢中断，改一次加载后22050原训练拍/31928原验证拍的x/rr/y/subject逐字节一致，未改数据或分数。

说明在docs/cnn_patient_cv.md，结果/失败在docs/records/cnn_patient_cv_20261017.md，备份tmp/backup/cnn_cv_docs_20261017_01。计划将来源/患者CV实验标完成，将合格四分类、受控后续训练、INT8和PL仍保留未完成。独立6人测试没有开封标记或预测，没有训练全量最终模型、量化、部署、发布或操作Git/Computer Use/板卡/Flash。根README、资料索引、latest及11项QRS冻结哈希检查保持一致；文档全库另有未修改HDMI.md行号锚点报错，本轮文档链接正常。smoke仍未上板测试，专家切拍分类不代表自动检测或真实输入链路验收。

### 2026-10-17：v9目标来源微调、患者权重和训练比例校正

用户在v8后要求继续。先读当前规则、代码和完整结果，冻结data/cnn_target_adapt_v9_protocol.json，SHA3b831db2fcdc82cb5601034e67338cd2e87d4ee7def1e8b09318ee701063e4e2。新增data/freeze_cnn_adapt.py、data/train_cnn_adapt.py与sim/test_cnn_adapt.py、sim/verify_cnn_adapt.py；保留全部v8文件和失败结果。仍用26名开发患者原三折，独立6人测试完全排除，每折只能加载自己v8 residual_verified权重与训练RR统计。

比较base原权重、natural普通损失微调、patient患者/类别平方根权重微调；后两者只用当前折INCART训练患者，N每患者最多2000，其余全部保留，验证不截断。相同初始化、低学习率1e-4、AdamW/weight_decay1e-3、既有增强、batch256、CPU4、固定seed2026101709+fold、12—25轮/耐心6。仅按alpha0验证macro-F1选checkpoint。每阶段再比较预先冻结的alpha0/0.5/1输出比例校正，目标比例只从本折完整训练患者计算，不用验证标签或测试；条件分布不变、训练收敛等假设未保证，不能称得到已校准真实概率。

六次微调共91轮，三阶段×三alpha共9方案27折分数，全不合格。按预定三折平均macro-F1仍选base alpha0=0.641363，旧权重对照逐拍复现v8。新微调中natural alpha0.5三折平均0.629485，合并OOF0.665553，S F1从0.4367升0.5900，但S召回86.870%降67.175%、F召回44.720%降18.012%，F1降至0.1514。patient alpha1合并OOF最高0.667731，但三折平均0.605710、F召回仅16.770%；不能看到汇总更高就改选型规则。第一折base半强度校正F精确率54.0%升92.9%但召回56.7%降21.7%，完整结果证实误报减少常伴随更多漏分，不报为成功。

3项软件检查通过，验证患者权重/排列、训练比例不受验证标签影响、训练N截断、校正和非法输入；4份Python语法通过。独立检查重构采样/损失权重/比例、患者分离和各项哈希，从9组权重重放431748个原始验证样本、1295244条校正预测，原始logits容差检查和所有预测/逐类/逐患者指标/门槛/选择均通过。证据tmp/cnn_adapt_verification_20261017.json及docs/records/cnn_adapt_verification_20261017.log，决策SHA e1602203d4bc90efb4545e6432f2c5d29a76e9880215852ddb526faca00a5b9a；检查通过只说明比较可信，不等于模型达标。

代码、参数、权重、训练索引/损失权重、原始logits及全部alpha预测放tmp/cnn_target_adapt_v9_20261017_01，失败全保留。说明docs/cnn_target_adapt.md，实际日志/表格/混淆矩阵/分析docs/records/cnn_target_adapt_20261017.md；更新data/README、docs导航/CV说明与计划。文档写前备份tmp/backup/cnn_adapt_docs_20261017_01，保留新出现的HDMI导航等并发修改。40份Markdown/258链接检查仍仅未修改HDMI.md的#L181锚点报错，本轮链接、受保护README/资料索引/latest和11项QRS哈希通过；不把全库检查说成无错误。

本轮没有新依赖/预训练权重下载、Git、Computer Use、板卡/Flash或发布操作；训练结束时6名独立测试仍未评估，没有全量最终拟合、INT8或PL部署。四分类仍未合格，已把进一步审查因果邻拍/患者背景表示或有效F患者来源列为待办，不以继续相同轮次/固定比例变换冒充解决。smoke仍未上板测试。

### 2026-10-17：标签无关历史背景、完整重建及冻结支路训练

用户要求按前轮方向继续改。新增src/reference/ecg_causal_background.py与ecg_context_cnn.py、data/prepare_cnn_background.py与train_cnn_background.py，冻结v10协议2fb7c2c9d0983cee604025e49a3b2567536426e3d156704b8451e5a4929575bd。背景取此前最多8个完整窗口逐点中位数，必须满足原生窗口结束R+ceil(fs*后窗)<=当前R；每记录重置，使用全部心拍而不按N/S/V/F选择模板，无历史给零/count0不删除评分拍。仍依赖专家心拍位置，当前拍等待原约533ms后窗，不能称自动QRS或端到端通过。

首次缓存生成在I35首标注(-15,V)被last_time=-1误拒绝，查明是合法负位置首标注且后续递增；改用None初始状态并补测，未动原始标注或删除记录。失败01目录/日志保留，最终02缓存开发143916拍、MIT辅助30842拍；背景参考240846个完整窗口，无背景46/5拍保留。新缓存原x/rr/y/记录/患者/R位置/代码/采样单位与父缓存逐字节相同。独立检索算法不用队列状态机重建174758个背景/计数/末端，全量一致；源文件官方SHA及导联首值/模和核对。数据证据tmp/cnn_background_parent_match_20261017.json、tmp/cnn_background_data_verification_20261017.json与对应docs/records日志。

v10同样本/初始父权重/损失/种子比较当前拍与新增历史支路，全量更新；新卷积/RR支路零初始化，增加232参数，起始预测核对与本折v8父模型一致。6次各18轮合计108轮，所有最优都为epoch0，更新后验证均未超过父模型。第一折没有收益后另立v11协议64a0fb5ca1156c316cedf23042662a15e83d2540381c50872288497671fe3bf5，只训练新支路232参数、主干逐字节冻结；lr0.001/新seed/12—25轮，不能只将差异归因冻结。三次各12轮36轮，同样全部最优epoch0。两轮9次144轮，候选最佳三折平均0.641363、合并OOF0.623916，S/F F1为0.436667/0.168618，未合格；保存最佳checkpoint为父模型/零新支路，不把它称为已学会历史表示，未声称保存每个舍弃epoch的权重。

5项功能检查在数据环境2通过/3缺Torch跳过，Torch环境4通过/1缺WFDB跳过，互补覆盖5项：可用时刻/负首位置/记录重置、当前R后原波形扰动不影响背景、零支路父模型等价及可训练、同步增强、冻结主干不变。8份Python语法通过；本机Python3.14.7/CPU PyTorch2.14.1+cpu/NumPy2.5.2与既有WFDB/SciPy环境，未安装新依赖。模型独立重放v10 287832条、v11 143916条，合计431748个验证预测与保存结果一致，采样/患者隔离、RR来源、CE/逐类/逐患者指标、门槛、初始checkpoint与代码/权重哈希均通过；v11还逐项检查原参数未变。检查通过说明结果可信，不证明新表示有效。

训练模型/缓存/源码快照/日志与预测留tmp/cnn_background_v10_20261017_01、tmp/cnn_background_adapter_v11_20261017_01等，不删历史；正式工程说明docs/cnn_background.md，完整失败/矩阵与证据docs/records/cnn_background_20261017.md。更新data/README、docs导航/微调说明和计划，文档备份tmp/backup/cnn_background_docs_20261017_01，保留HDMI导航并发改动。42份Markdown/282链接检查仅未修改HDMI.md行号锚点报错，本轮链接/根README/资料索引/latest和11项QRS哈希正常。

历史架构12684总参数、635296Conv/Linear MAC/拍，v11只训练232不等于部署只需232；预算排除历史缓存、中位数和预处理/传输，未做7020实测或综合。此方案本轮未获得验证收益，不建议继续相同表示加轮次；下一阶段先审查F患者覆盖、跨来源形态/标注位置和当前输入可分性。保留6名独立测试未用，未最终全量拟合、INT8、PL、板卡/Flash、Git、Computer Use或发布；smoke仍未上板测试。

### 2026-10-17：结构归档与模型训练交接

用户要求规范结构、把不用内容放tmp，准备交接模型训练；本轮停止增加训练实验。读取规则、当前文件/导入和最近结果，Win32_Process未发现Vivado/Vitis/Python/Java/loader/hw_server活动进程。按依赖保留当前v8、v6/v7父数据准备以及仍被调用的旧名公共函数文件，不为了归档改冻结源码或哈希。

32个旧专属脚本/协议/测试或工具目录可恢复移至tmp/history/training_handoff_20261017，293文件/43857578字节，逐文件SHA256一致，保留67项工程/协议/发布哈希一致。旧AC7020脚本是转发领航者的兼容包装；旧根vivado/_ide/.rigel_lopper/.Xil/torchinductor均归档，XPR内部历史路径未改。当前smoke/QSPI工作区、数据/环境/全部训练结果未移动；文字记录仍在docs/records。映射和校验在归档manifest.json，文档写前副本tmp/backup/training_handoff_20261017。

更新data/sim/build说明、历史教程提示与迁移链接、docs导航、计划和myself旧bit路径；新增docs/model_training_handoff.md与data/package_training_handoff.py。接手入口、输入/类别/患者/独立测试边界、对照权重、命令及交回要求均明确。生成含开发缓存/完整v8对照/文本工程和SHA清单的本地ZIP，不带原始数据、环境、独立测试缓存、旧工具工程或板卡镜像，不发送上传。历史恢复需在另一项目副本按原位置恢复，归档目录不直接执行。

数据环境44项测试34通过/10跳过，Torch环境34项22通过/12跳过，跳过因各环境缺不同依赖；37份Python语法及归档模块导入检查通过。原路径和实际解压后另一目录分别完整重放12组权重575664条已知开发预测，逐拍/逐类/逐患者/哈希/RR/门槛/选型一致，无新训练；源码和数据不变，因此分类分数不变、仍未合格。解压文件345项SHA一致，同机改路径不等于另一台电脑实测。详细记录docs/records/structure_handoff_20261017.md，相关原始日志同目录，最终包/校验在tmp/handoff。

全库44份Markdown/306链接检查发现4处指向缺失HDMI.md（README一处，新uart_protocol.md三处）；这些文件属于其他工作，本轮未移动/恢复，保留并发状态，未声称全库链接通过。当前根README/资料索引/latest保护及11项QRS冻结SHA通过，Git持续暂停。独立6人测试未使用，四分类仍未合格，无最终全量模型、INT8、PL或板卡/Flash操作；smoke仍未上板测试。

### 2026-10-17：按一般模型开发流程补全训练计划

用户指出模型类不只训练/量化/交接，应包含从零建立或复用对照的完整步骤。本轮将C01—C13按任务/标准、可复用资料、数据质量、划分协议、预处理、基线对照、实验设计、调试训练、验证诊断迭代、冻结独立测试、INT8、导出复现及端到端集成组织。明确已有阶段可复核复用，不要求废弃成果从零重来；对照模型用来判断改动收益，不替代专家标注。若复用外部权重还要核查其训练患者与测试集重叠。失败四分类和新6人测试边界保留，不因计划完善恢复训练或加载CLEF。

同步前两次用户纠正，滤波/工频与采集输出归A06—A08，项目主体明确电脑通信显示并使用C11整数参考。备份tmp/backup/model_workflow_plan_20261017_01；本次仅计划和本日志两文件变化，教程、根README、资料索引、源码、发布和Git索引保护。任务编号/跨类引用、Markdown链接和保护哈希检查见tmp/model_workflow_plan_verification_20261017.json；未训练、测试模型或操作板卡，没有新准确率/性能结果，未提交推送。

### 2026-10-17：记录模型增强与7020资源选型原则

用户要求把板卡是否能运行更高级网络的讨论写入计划。本轮在report/model.md新增3.5节：当前小网络作固定对照，先查数据/输入/逐类误判，再按假设适度增强，使用患者隔离开发验证评估收益；对有收益候选核算INT8、权重/激活缓冲、算子、带宽与延迟，再交主体B05核实。记录官方7020总资源和当前12,452参数/606,616次Conv/Linear MAC每拍的预算来源，不把它写成剩余资源、实测性能或资源已经到顶。已有100k参数门槛不冒称硬件上限，变更须另立确认的协议。

仅增加计划待办，不勾选模型增强/量化/硬件结果，不恢复训练、不读独立测试、不安装或操作板卡。备份tmp/backup/model_capacity_plan_20261017_01；核对原任务/勾选保留、新链接及受保护文件哈希，摘要tmp/model_capacity_plan_verification_20261017.json。当前四分类仍未合格、CNN硬件实现未验，未提交推送。

