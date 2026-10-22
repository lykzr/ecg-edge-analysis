"""项目路径和独立记录目录；不依赖启动工作目录或成员盘符。"""
from datetime import datetime
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT/'tmp/pc_monitor_logs'

def new_directory(base=DEFAULT_OUTPUT):
    return Path(base)/(datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:8])
