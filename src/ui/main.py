"""电脑界面启动入口；兼容旧入口的命令行参数，不操作板卡复位或Flash。"""
from pathlib import Path
import sys

# 仅启动入口建立模块搜索路径，支持从任意工作目录直接运行。
SOURCE = Path(__file__).resolve().parents[1]
for directory in (SOURCE, SOURCE/'pc'):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
from ecg_monitor import main

if __name__ == '__main__':
    raise SystemExit(main())
