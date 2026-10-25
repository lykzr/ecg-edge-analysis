# 可复用工程技能包

面向陌生队伍、开发者或AI助手，按AMD自主选题指南3.3.5.2提供可复制的校验工具和诊断流程。不依赖原作者电脑、聊天、ECG数据或历史tmp；不是安装Codex插件的要求，不声明通用PYNQ加分资格。

| 项目 | 使用入口 | 适用与边界 |
| --- | --- | --- |
| [交付文件校验](artifact-check/SKILL.md) | [校验脚本](artifact-check/scripts/check_files.py) | 任意文件集的SHA/字节校验；不证明来源真实性或板卡匹配 |
| [黄金参考比对](trace-check/SKILL.md) | [比对脚本](trace-check/scripts/compare_csv.py) | 同时轴CSV，默认精确比较；不自动对齐，不替代准确率 |
| [下载与启动排查](download-diagnose/SKILL.md) | 人工排查表 | 工作目录、器件、镜像头、编程与冷启动分级；硬件参数须取自自己的资料 |

每项SKILL.md分别列出适用、方法、失败来源、已验证效果与失效条件。可以只复制需要的子目录；脚本仅用Python3.10及以上标准库，不导入ECG工程或第三方包。

## 快速使用

从仓库根检查现有发布（只读、不连板）：

```text
python -B skill/artifact-check/scripts/check_files.py --root releases/latest --manifest releases/latest/manifest.json
```

同表头、同序号CSV比较：

```text
python -B skill/trace-check/scripts/compare_csv.py --reference golden.csv --candidate actual.csv --key cycle
```

具体JSON/CSV合同与退出码见对应SKILL.md；复制到其他工程时替换文件路径和预先冻结的容差，不照搬ECG采样率、幅值、寄存器、端口或拨码。

## 验证与来源

运行`python -B -m unittest discover -s sim -p test_skills.py`。测试只复制skill到独立含空格路径，使用另一个工程作工作目录，验证成功、篡改、缺失、换行、越界、序号、容差、NaN及大整数等行为；不安装或操作硬件。效果与旧案例见[验证记录](../docs/records/skill_20261025.md)。独立复制技能目录无需取得这些历史记录。

已有ECG仿真、Flash及Git案例仅作为经验来源；新通用脚本不自动继承原硬件成绩。当前在Windows/Python实跑，尚未验证Linux/macOS、第二板卡或PYNQ。原始提示词、模型回答、自我纠错仍需另行整理，不能以技能总结替代。
