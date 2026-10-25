---
name: artifact-check
description: 按字节数与SHA256验证工程交付清单，定位复制、Git换行或混用产物造成的不一致。
---

# 交付文件校验

适用：软件、FPGA镜像、测试向量等需要按原字节交接的文件集；不依赖ECG、特定板卡、AMD工具或第三方Python包。

## 使用

1. 从提供方取得已冻结、来源可信的清单；失败时保留原文件和清单，不就地重算清单掩盖差异。
2. 下面是格式示意，不是可直接执行的清单；替换字节数和SHA后，将JSON保存在待交付文件根目录旁或目录中，路径相对传入的root，必须用正斜杠。清单不包含自身SHA。

```json
{"files":{"firmware.bin":{"bytes":1234,"sha256":"提供方计算的64位十六进制SHA256"}}}
```

3. 从本技能子目录（包含SKILL.md和scripts的目录）执行Python3.10及以上标准库脚本：

```text
python scripts/check_files.py --root <文件根目录> --manifest <清单JSON>
```

脚本只读，JSON输出passed/files/bytes，通过退出0，缺失/篡改/越界退出1。清单只覆盖列出的文件，不拒绝目录中额外文件。可先用本仓库示例：从仓库根运行`python skill/artifact-check/scripts/check_files.py --root releases/latest --manifest releases/latest/manifest.json`。

4. Git交接应从实际提交新克隆到没有旧缓存的位置，再执行同一校验。若文件字节因core.autocrlf变化，先查属性与原始来源；只对确实需保留字节的文件规定Git换行策略，不把本项目的全局策略强加给其他项目。

## 效果与失败来源

本项目最初从工作区复制通过，Git索引副本却因自动换行改变源码/证据/模型记录而失败。恢复原字节并固定属性后，真实Git克隆的发布与冻结检查通过。具体旧案例见仓库`docs/records/qspi_20261025.md`、`data/results/handoff_20261025.json`；新通用脚本的成功/篡改/缺失/路径逃逸用例见`sim/test_skills.py`及`docs/records/skill_20261025.md`。这些案例路径只用于追溯，独立复制此技能无需它们。

## 失效条件

攻击者同时替换文件和清单仍可通过，SHA不证明来源可信。文件相同不证明硬件匹配、许可、算法准确率或启动成功。本脚本不校验镜像语义，不下载、不写Flash；文件检查后若仍有其他进程修改文件，需要停止写入再重新验证。
