"""Vitis入口：独立USB_UART接收应用；复用匹配500Hz硬件，不连接板卡。"""
import os
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
os.environ['ECG_STREAM_APP'] = 'ecg_bridge'
os.environ.setdefault('ECG_STREAM_WORKSPACE', str(ROOT/'tmp/ecg_bridge/vitis_workspace'))
runpy.run_path(str(ROOT/'board/build_ecg_stream.py'), run_name='__main__')
