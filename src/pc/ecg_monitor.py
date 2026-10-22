"""PC无界面接收/回放命令行；无参数时兼容启动src/ui界面。"""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import uuid

SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
from ecg_paths import ROOT, DEFAULT_OUTPUT, new_directory
from ecg_monitor_core import Monitor, Recorder, RecordingLimitError, demo_frames
from ecg_serial import SerialCapture
from ui.plot import save_svg

def headless(args):
    output = args.output_dir or new_directory()
    monitor = Monitor(Recorder(output, args.max_bytes))
    reason = 'completed'; code = 0
    capture = None
    try:
        if args.serial:
            capture = SerialCapture(monitor, args.serial, args.baud)
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                capture.poll()
                time.sleep(.01)
        elif args.demo:
            monitor.input_info = {'kind': 'demo'}
            for _, data in demo_frames(args.seconds, args.fs, None if args.scale == -1 else args.scale, 'demo-' + uuid.uuid4().hex[:8]):
                monitor.feed(data)
        else:
            monitor.input_info = {'kind': 'replay', 'path': str(args.replay)}
            with args.replay.open('rb') as stream:
                for data in iter(lambda: stream.read(4096), b''):
                    monitor.feed(data)
        if not monitor.counts['samples']:
            reason = 'no_waveform_data'; code = 2
    except (OSError, ValueError) as error:
        reason = ('recording_limit: ' if isinstance(error, RecordingLimitError) else 'input_or_io_error: ') + str(error)
        code = 2
    except KeyboardInterrupt:
        reason = 'interrupted_by_user'; code = 130
    finally:
        if capture:
            try:
                capture.close()
            except OSError as error:
                reason += '; close_error: ' + str(error); code = 2
    summary = monitor.finish(reason)
    if code == 0:
        save_svg(monitor, Path(output) / 'waveform.svg')
    print(json.dumps({'output_dir': str(output), **summary}, ensure_ascii=False))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--demo', action='store_true'); group.add_argument('--replay', type=Path)
    group.add_argument('--serial', metavar='COM_PORT', help='Windows串口只收，需--headless')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--headless', action='store_true'); parser.add_argument('--ui-self-test', action='store_true')
    parser.add_argument('--seconds', type=float, default=10); parser.add_argument('--fs', type=int, default=360)
    parser.add_argument('--scale', type=int, default=-1)
    parser.add_argument('--output-dir', type=Path); parser.add_argument('--max-bytes', type=int, default=64*1024*1024)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 3600:
        parser.error('--seconds须为0..3600内的有限秒数')
    try:
        if args.ui_self_test:
            from ui.monitor import ui_self_test
            return ui_self_test(args)
        if args.headless:
            if not (args.demo or args.replay or args.serial):
                parser.error('--headless需要--demo、--replay或--serial')
            return headless(args)
        if args.demo or args.replay or args.serial or args.output_dir:
            parser.error('命令行批处理请加--headless；GUI请直接运行后点击按钮')
        from ui.monitor import Application, enable_windows_dpi_awareness
        enable_windows_dpi_awareness()
        import tkinter as tk
        root = tk.Tk(); Application(root); root.mainloop()
        return 0
    except (OSError, ValueError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
