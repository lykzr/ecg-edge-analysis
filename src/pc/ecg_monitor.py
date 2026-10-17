"""PC离线监视器：Tkinter演示/日志回放与无界面核验；没有真实串口输入。"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
import uuid

from ecg_monitor_core import Monitor, Recorder, RecordingLimitError, demo_frames, plot_geometry, save_svg

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / 'tmp/pc_monitor_logs'


def new_directory(base=DEFAULT_OUTPUT):
    return Path(base) / (datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8])


def headless(args):
    output = args.output_dir or new_directory()
    monitor = Monitor(Recorder(output, args.max_bytes))
    reason = 'completed'; code = 0
    try:
        if args.demo:
            for _, data in demo_frames(args.seconds, args.fs, None if args.scale == -1 else args.scale, 'demo-' + uuid.uuid4().hex[:8]):
                monitor.feed(data)
        else:
            with args.replay.open('rb') as stream:
                for data in iter(lambda: stream.read(4096), b''):
                    monitor.feed(data)
        if not monitor.counts['samples']:
            reason = 'no_waveform_data'; code = 2
    except (OSError, ValueError) as error:
        reason = ('recording_limit: ' if isinstance(error, RecordingLimitError) else 'input_or_io_error: ') + str(error)
        code = 2
    summary = monitor.finish(reason)
    if code == 0:
        save_svg(monitor, Path(output) / 'waveform.svg')
    print(json.dumps({'output_dir': str(output), **summary}, ensure_ascii=False))
    return code


class Application:
    def __init__(self, root, monitor=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk; self.root = root
        self.monitor = monitor or Monitor()
        self.running = False; self.input_file = None; self.frames = None; self.pending = None
        self.output = None; self.kind = None
        root.title('ECG PC离线监视器 · 未连接板卡')
        root.geometry('1140x760'); root.minsize(960, 650)
        self.source_text = tk.StringVar(value='离线模式：演示事件是指定标记，不是检测或分类结果')
        ttk.Label(root, textvariable=self.source_text, foreground='#9b3e10', wraplength=1050).pack(anchor='w', padx=12, pady=8)
        toolbar = ttk.Frame(root); toolbar.pack(fill='x', padx=12)
        for title, action in [('开始演示', self.start_demo), ('打开日志回放', self.open_file),
                              ('停止并保存', self.stop), ('导出当前SVG', self.export)]:
            ttk.Button(toolbar, text=title, command=action).pack(side='left', padx=(0, 8))
        self.info_text = tk.StringVar(value='等待数据；采样率/单位/分类未提供')
        ttk.Label(root, textvariable=self.info_text, wraplength=1050).pack(anchor='w', padx=12, pady=6)
        self.canvas = tk.Canvas(root, background='#101820', height=350, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=12)
        self.canvas.bind('<Configure>', lambda _: self.draw())
        self.metrics_text = tk.StringVar()
        ttk.Label(root, textvariable=self.metrics_text, wraplength=1050).pack(anchor='w', padx=12, pady=6)
        self.table = ttk.Treeview(root, columns=('evt', 'pos', 'rr', 'hr', 'cls'), show='headings', height=5)
        for name, title in [('evt', '事件号'), ('pos', '候选/演示位置'), ('rr', 'RR样本数'), ('hr', '心率'), ('cls', '类别')]:
            self.table.heading(name, text=title); self.table.column(name, width=140, anchor='center')
        self.table.pack(fill='x', padx=12)
        self.message_text = tk.StringVar(value='默认记录到tmp/pc_monitor_logs；不覆盖旧目录。此版本不打开串口。')
        ttk.Label(root, textvariable=self.message_text, wraplength=1050).pack(anchor='w', padx=12, pady=8)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.draw()
        root.after(40, self.tick)

    def start_demo(self):
        self.start('demo')

    def open_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title='选择ECG-UART-1原始行日志', filetypes=[('日志', '*.log *.txt'), ('全部文件', '*')])
        if path:
            self.start('file', Path(path))

    def start(self, kind, path=None):
        from tkinter import messagebox
        self.stop()
        try:
            self.output = new_directory()
            recorder = Recorder(self.output)
            self.monitor = Monitor(recorder)
            self.kind = kind
            if kind == 'demo':
                self.frames = iter(demo_frames(60, 360, None, 'demo-' + uuid.uuid4().hex[:8]))
                self.pending = next(self.frames); self.started = time.monotonic()
                self.source_text.set('数学合成演示 · 未连接板卡 · 未运行QRS/CNN · 未提供滤波与分类 · 未标定电压')
            else:
                self.input_file = path.open('rb')
                self.source_text.set('离线日志快速回放（按序处理，非墙钟实时） · 不证明文件来源真实或板卡已连接')
            self.running = True
            self.message_text.set('原始与CSV记录：' + str(self.output))
        except (OSError, ValueError) as error:
            self.running = False
            if self.monitor.recorder and not self.monitor.recorder.closed:
                self.monitor.finish('start_error: ' + str(error))
            messagebox.showerror('无法开始', str(error))

    def tick(self):
        if self.running:
            try:
                if self.kind == 'demo':
                    count = 0
                    while self.pending is not None and self.pending[0] <= time.monotonic() - self.started and count < 32:
                        self.monitor.feed(self.pending[1]); count += 1
                        self.pending = next(self.frames, None)
                    if self.pending is None:
                        self.stop('completed')
                else:
                    chunk = self.input_file.read(4096)
                    if chunk:
                        self.monitor.feed(chunk)
                    else:
                        self.stop('completed' if self.monitor.counts['samples'] else 'no_waveform_data')
            except (OSError, ValueError) as error:
                self.stop('input_or_record_error: ' + str(error))
            self.draw()
        self.root.after(40, self.tick)

    def stop(self, reason='stopped_by_user'):
        was_running = self.running
        self.running = False
        if self.input_file:
            self.input_file.close(); self.input_file = None
        if self.monitor.recorder and not self.monitor.recorder.closed:
            try:
                self.monitor.finish(reason)
                display_reason = '没有ECG-UART-1波形；smoke文本自检日志不是波形流' if reason == 'no_waveform_data' else reason
                self.message_text.set(f'已停止：{display_reason}；记录位于 {self.output}')
            except OSError as error:
                self.message_text.set('记录关闭失败（磁盘/权限），已有文件保留：' + str(error))
        elif was_running:
            self.message_text.set(reason)

    def export(self):
        from tkinter import filedialog, messagebox
        path = filedialog.asksaveasfilename(title='保存当前SVG（不覆盖已存在文件）', defaultextension='.svg', filetypes=[('SVG', '*.svg')])
        if path:
            try:
                save_svg(self.monitor, path)
            except OSError as error:
                messagebox.showerror('导出失败', str(error))

    def draw(self):
        canvas = self.canvas; canvas.delete('all')
        width = max(canvas.winfo_width(), 900); height = max(canvas.winfo_height(), 330)
        g = plot_geometry(self.monitor, width, height)
        for i in range(1, 6):
            y = 30 + i * (height - 72) / 6
            canvas.create_line(64, y, width - 20, y, fill='#283744')
        for name, color in [('raw', '#58d6a6'), ('filt', '#70baff')]:
            for segment in g[name]:
                canvas.create_line(*[v for point in segment for v in point], fill=color, width=1.4, tags='wave')
        for x, seq in g['events']:
            canvas.create_line(x, 30, x, height - 42, fill='#ffcd70', dash=(4, 4), tags='event')
            canvas.create_text(x + 4, 32, text=str(seq), fill='#ffcd70', anchor='nw')
        canvas.create_text(12, 10, text=g['unit'] + '；绿色raw / 蓝色filt（缺失不画）', fill='#eeeeee', anchor='nw')
        canvas.create_text(64, height - 24, text=f"{g.get('first', 0):.3f} → {g.get('last', 0):.3f} {g['time_unit']}；接收时间不作采样时间", fill='#eeeeee', anchor='w')
        h = self.monitor.header
        if h:
            fs = '未提供' if h.fs is None else str(h.fs)
            hr = '未提供' if self.monitor.hr is None else f'{self.monitor.hr:.1f}'
            rr = '未提供' if self.monitor.rr_ms is None else f'{self.monitor.rr_ms:.1f}ms'
            self.info_text.set(f'来源声明 {h.source} | 检测器 {h.detector} | fs {fs} | {g["unit"]} | 心率 {hr} | RR {rr} | 类别 {self.monitor.cls} | session {h.session}')
        c = self.monitor.counts; p = self.monitor.decoder.counts
        status = self.monitor.status
        event_drop = '未提供' if status is None or status.event_drop is None else str(status.event_drop)
        self.metrics_text.set(f'累计样本 {c["samples"]} / 事件 {c["events"]} | 接收段波形缺口 {c["wave_gap"]} / 事件缺口 {c["event_gap"]}（不推断首帧前） | FIFO丢事件 {event_drop} | 坏行 {p["invalid"]} / 超长 {p["overlong"]} / 非协议 {p["unknown"]} | {self.monitor.decoder.last_error}')
        self.table.delete(*self.table.get_children())
        for event in list(self.monitor.events)[-5:]:
            self.table.insert('', 'end', values=(event.seq, event.pos, event.rr, '未提供' if event.hr is None else f'{event.hr:.1f}', event.cls))

    def close(self):
        self.stop('window_closed'); self.root.destroy()


def ui_self_test(args):
    import tkinter as tk
    output = args.output_dir or new_directory()
    monitor = Monitor(Recorder(output, args.max_bytes))
    for _, data in demo_frames(3.01, session='ui-self-test'):
        monitor.feed(data)
    monitor.finish('ui_self_test')
    root = tk.Tk(); root.withdraw()
    try:
        app = Application(root, monitor)
        app.source_text.set('隐藏窗口自检：数学合成源，非实测')
        root.update_idletasks(); app.draw()
        assert app.canvas.find_withtag('wave') and app.canvas.find_withtag('event')
        assert '未标定' in app.info_text.get() and '类别 ?' in app.info_text.get()
        assert len(app.table.get_children()) == len(monitor.events)
        result = {'passed': True, 'tk': root.tk.call('info', 'patchlevel'),
                  'samples': monitor.counts['samples'], 'canvas_wave_items': len(app.canvas.find_withtag('wave')),
                  'canvas_event_items': len(app.canvas.find_withtag('event')), 'scope': 'hidden-window construction; not manual usability or serial test'}
        save_svg(monitor, Path(output) / 'waveform.svg')
        (Path(output) / 'ui_check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output_dir': str(output), **result}, ensure_ascii=False))
    finally:
        root.destroy()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--demo', action='store_true'); group.add_argument('--replay', type=Path)
    parser.add_argument('--headless', action='store_true'); parser.add_argument('--ui-self-test', action='store_true')
    parser.add_argument('--seconds', type=float, default=10); parser.add_argument('--fs', type=int, default=360)
    parser.add_argument('--scale', type=int, default=-1)
    parser.add_argument('--output-dir', type=Path); parser.add_argument('--max-bytes', type=int, default=64*1024*1024)
    args = parser.parse_args()
    try:
        if args.ui_self_test:
            return ui_self_test(args)
        if args.headless:
            if not (args.demo or args.replay):
                parser.error('--headless需要--demo或--replay')
            return headless(args)
        if args.demo or args.replay or args.output_dir:
            parser.error('命令行批处理请加--headless；GUI请直接运行后点击按钮')
        import tkinter as tk
        root = tk.Tk(); Application(root); root.mainloop()
        return 0
    except (OSError, ValueError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
