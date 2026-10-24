# 主体后续：标准仿真、重建与故障状态

## 范围与更正

2026-10-24按用户“做”继续主体准备，不恢复QRS/CNN调参，不操作板卡或Git。根README、资料索引、旧latest和冻结算法保留。

上一轮XSim的DLL重定位及引擎崩溃发生在受限执行上下文；本轮在允许本地工具执行的正常上下文，未改安装/编译器/权限，同一快照及标准Vivado全流程均通过。因此“本机安装/编译器损坏”的归因证据不足，追加更正，旧失败不删除。标准日志tmp/system_next_20261024_01/int8_standard；进一步严格X比较、近INT32界、busy重复start及池化末尾覆盖见int8_strict，2688卷积/312池化/8复位全部通过。

## 已完成子项

- 真实XSim逐值仿真通过，不是Python替代RTL；没有模型或分类准确率声明。
- PC中转摘要增加合法W之后的接收间隔sample_age_s，非采样时钟/断连证明；中转窗口陈旧心率标历史，错误显示红色。主窗口即使继续收到其他日志、但没有新波形，也将数值标为历史。5项状态/隐藏Tk检查通过，人工视觉和真实拔插仍未验。
- 初次隐藏Tk测试的人造时钟未重置构造窗口时的真实时刻，出现断言失败；修正测试起点后重跑通过，不把它说成实物故障。
- 当前设计开发稿report/design.md只整理已验框图、分工、接口、证据及局限，不填最终模型/性能或原始协作交互。
- 许可检查扫描已有工作区1492份源/头/构建文本，213份列在编译命令中；生成目录包含GPL/双许可文件，当前列出编译源中未见GPL声明，但未完成最终二进制全审。保留MIT版权、Eric Young MD5、FatFs与Cygnus原声明，详见docs/licenses.md。不能把所有BSP/FSBL笼统称MIT。

## 当前完整重建

新增build/rebuild_system.tcl、board/rebuild_system.py，从新目录复用原板级配置，显式比较正式BD的全部PS7和ECG参数，导出新bit/XSA/初始化及ARM ELF/链接图。新产物不自动替换latest。

直接Python/BAT封装最初发生用户TclApp缓存“Could not open C for writing”，按Xilinx官方TclStore说明对子进程设置XILINX_LOCAL_USER_DATA=no，不修改全局环境或用户缓存。其后Python/BAT启动出现原RTL层次解析失败；最小模块、ASCII注释副本及原始中文注释批量装载的对照均能识别，不能归因RTL算法或中文注释错误。手动source_mgmt_mode尝试不支持BD模块引用，已撤回；无帮助的check_syntax顺序尝试也已撤回。保留了明确的依赖装载/顶层顺序，原生PowerShell调用成功生成BD并进入综合/实现。封装改为原生PowerShell独立参数，支持显式--hardware-from接续来源；尚不能把未完成的封装全链称验收通过。

失败目录tmp/rb360_01..06、08及最初tmp/system_next_20261024_01/rebuild_01保留；当前原生新硬件目录tmp/rb360_07，日志在tmp/system_next_20261024_01/native_build.log。此阶段PS7/ECG全部参数与正式BD逐项相同；构建完成结果后续追加，不提前勾选。

官方缓存说明：[Xilinx TclStore](https://github.com/Xilinx/XilinxTclStore/wiki/Adding-a-New-App-to-the-Repository)，只用于解释缓存开关，不继承其中Git/安装指令。

## 接续构建与最终核对

17点后的接续核对发现原生进程已不在、日志停在额外report_drc；其前的实现、bit生成已完成，原因未证实，不把进程消失说成DRC违规。用新Tcl显式打开同一已完成工程导出XSA/bit/ps7_init及逐路径时序。保存实现阶段已有的同一布线DRC报告（零项违规），正式构建入口也复用该报告，避免重复扫描。最终时序摘要为setup 0.329ns、hold 0.057ns，无负裕量；不使用之前布线过程的估算值充当最终报告。

软件第一次在深层`tmp/system_next_20261024_01/rebuild_finish_01/vitis_workspace`创建平台失败，报Invalid project location。Vitis BAT退出码仍为0，但检查脚本因缺build_manifest明确失败，未报成功。保留失败目录，在短路径`tmp/rbsw01`用同一新XSA重建成功；这支持路径相关判断，未证明所有错误都由路径长度导致。正式说明推荐短路径，不改权限/安装器。

成功证据：`tmp/rbsw01/summary.json`、`tmp/rbsw01/vitis_workspace/build_manifest.json`和`tmp/rb360_07/hardware/`。bit为4045773字节/SHA256 `81403a462b74514265b4dc4e36798813f602df6be29319bd87233507f27fa40e`；XSA为321429字节/`70de5600b4944e967360bb2e133e007903bd963b5bb64cf025bfca86948b2ab8`；ARM ELF为420056字节/`b795923a7fcf36fe34adadf15754a1e32ef89eb4f693185a932c14fb67423922`；build_id `f697e8ba12984127`。链接图261233字节，实际存在且已纳入清单；FSBL359036字节另作证据核对。编译有既有源码警告，构建成功不等于零警告或实板功能通过。

收尾回归第一次误用系统Python，缺WFDB/SciPy导致3个模块导入失败，保留regression_final，不将其说成全部通过。改用已有`tmp/qrs_benchmark_env/Scripts/python.exe`运行同一干净源码检查，`regression_final_qrs/summary.json`的14组全部通过，含真实隐藏Tk的5项新状态检查。复制353份正式文件，不依赖历史tmp产物；仍使用已安装的解释器/编译器和库，不等于新电脑安装验证。

本轮阶段重建由原生Vivado加显式导出接续、正式Python软件封装完成；更新后的单命令完整Vivado封装未另做全程复跑，保留该限制。旧latest、新QRS数学和模型均未修改，未连接/下载板卡、未写Flash、未Git操作。新镜像仅为离线候选，不能继承旧应用的实板成绩；新界面文案人工视觉、真实无线及最终模型/量化/PL推理仍待验。

最终接续清单：`tmp/system_next_20261024_01/final_checkpoint.json`。68项受保护文件SHA不变、XSA内部bit与单独bit逐字节哈希一致、应用所有导入源与正式源SHA一致；FSBL SHA256为`ce5056957debd6b6bc33c3513ae031e6fb80a66bda3cb5294082ccb36912330d`。正式交接静态检查353文件/147份Python解析通过，派生产物未加入正式源码清单；本机tmp中的构建结果不等于已通过Git交付二进制。
