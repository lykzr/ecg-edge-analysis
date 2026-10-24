# 新500Hz本地发布与下载入口收尾

2026-10-25，用户明确授权新版更新release、旧版归档、下载入口/教程同步，不提交推送。本轮仅本地文件发布，不写Flash，不改PS7/MIO/供电，不训练模型或调整QRS。

## 发布与来源

- 当前版本20261025-runtime500-jtag-v2，正常ELF构建a570b308ef7b46fe，SHA256 d7b948919b746333b145d90ce74d7be24e1e08964d52e6e07215c32baf0c77b9。
- 原latest的23个文件完整原字节归档到releases/history/20261024-runtime500-jtag-v1；源/目标均核对在项目内、历史目录不存在才移动，逐项SHA保留，无覆盖/删除。
- 新latest保留原smoke/bridge回归，runtime500更新为支持ADC的正常镜像，新增download.cmd与run_runtime500.ps1，25文件；不复制整套源码/文档/缓存。
- 新版独立数字证据为10412点CSV和重编码34字节模拟源分别经真实Zynq运行，均26事件、零削顶、完整确认/回传。旧窗口/高负载/错误验收保留其原构建身份，不冒充本新ELF已重做。
- 4份必要JTAG/UART原始日志已纳入docs/records/vendor500_board_20261025；原始用户CSV保留tmp，不复制发布或上传。正式不可变收据data/results/runtime500_release_20261025.json约束本ELF与日志。
- 新ELF/配套FSBL各自实际库与成员组成重新核对，精选清单data/results/runtime500_components_20261025.json；FSBL不随当前JTAG包分发。供应商补丁/IP最终分发仍未全审。

## 下载入口与教程

默认双击releases/latest/runtime500/download.cmd；PowerShell包装器按本目录清单核全部字节/SHA，再调用同目录Tcl，唯一板卡校验/临时JTAG/复位/匹配初始化仍保留。CheckOnly不连接板卡，不依赖作者tmp或Python；脚本用PSScriptRoot定位，支持复制到含空格目录。执行策略参数只作用于子进程，不改系统设置，不要求管理员。

docs/download_guide.md当前入口放在前部，vendor_input/runtime_board/bridge/pc_monitor和releases说明一并切换到release。旧360Hz、旧PL回归与从零构建仍按各自用途说明，不再把临时构建路径当默认用户操作。

## 未验边界

真实JDY18/双USB、实际寄存器/DRDY/标定、物理拔插与长时无线、新厂商界面人工检查、最终模型/INT8/FPGA推理/同模型性能仍未验。没有逐拍标注的26事件不报告准确率；105原风险未关闭。本地发布不代表Git提交/推送、远端公开发布或Flash掉电保存。


## 验证过程与更正

候选严格SHA、XSA嵌入bit与当前源码检查先通过，再归档替换。复制验收首次发现两个真实问题：Windows PowerShell由Python启动时不能自动找到Get-FileHash模块；以及候选third_party副本增加说明后不再匹配其正式来源。前者改为.NET流式SHA，无新增安装/模块；后者保持正式原声明字节，组成链接放用途README。原失败日志保留，修复后便携路径和篡改拒绝回归通过。

下载入口会先检测本机3121；缺服务则从所选XSDB同目录后台启动hw_server.bat，有界等待后才尝试下载。已有服务不重复启动，CheckOnly不触发探测或服务；实际冷启动分支尚未通过停止既有服务来重测，不擅自杀用户进程。每次运行仍由Tcl核对唯一下载器和xc7z020。


## 最终结果

- 20组干净源码检查通过，153项软件测试无跳过；使用默认严格发布模式，current_sources_match/current_release_rebuild_qualified均true，无源码漂移。不是靠artifact-only绕过。
- 10项发布测试通过，包括镜像/源码篡改拒绝、精确ignore、复制到含空格路径并从其他工作目录执行CheckOnly；篡改后的ELF会明确SHA256失败。
- 用正式打包入口重新生成候选，25文件与当前latest逐字节相同；不依赖旧工作区完成离线交接检查。
- 实际从tmp工作目录调用release自身download.cmd，唯一板卡校验后下载成功，COM14收到500Hz就绪身份；没有发送样本，串口已关闭，板端留待用户新会话。已有hw_server未重复启动；冷启动分支仍是未单独实物覆盖项。
- 原latest23文件归档SHA、根README/资料索引和29模型基线保护核对不变。没有Flash、Git暂存/提交/推送或原历史删除。

新入口原始日志位于同名记录子目录；精选收尾收据为[data/results/runtime500_download_20261025.json](../../data/results/runtime500_download_20261025.json)。用户现在可直接打开客户端，正常后续重跑则双击release入口，不再从tmp挑选文件。
