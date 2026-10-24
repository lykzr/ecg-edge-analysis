"""监视器主窗口与界面状态；数据/协议/记录逻辑由PC后台提供。"""
import json
import math
import os
from pathlib import Path
import time
import uuid

from ecg_monitor_core import Monitor, Recorder, RecordingLimitError, demo_frames
from ecg_serial import SerialCapture
from ecg_uart import CLASS, FILT
from ecg_ports import enumerate_ports, select_port, validate_port, remembered_identity, remember_identity
from ecg_paths import ROOT, DEFAULT_OUTPUT, new_directory
from .plot import plot_geometry, save_svg

STATE_STYLE = {
    'idle': ('未开始', '#5f6b76'),
    'demo': ('合成演示中', '#6b4fbb'),
    'replay': ('日志回放中', '#1f6fb2'),
    'serial_wait': ('串口已打开 · 等待数据', '#a35f00'),
    'serial_quiet': ('串口接收中 · 暂无新数据', '#a35f00'),
    'serial_live': ('串口接收中', '#1e7d46'),
    'stopped': ('已停止 · 显示历史数据', '#4a5560'),
    'error': ('已停止 · 出错', '#b3261e'),
}


SOURCE_HINT = {
    None: '选择数据来源：合成演示、日志回放或串口。本程序只显示收到的数据，不在电脑上运行QRS/CNN。',
    'demo': '数学合成波形：黄色竖线是预设标记，不是检测结果；未提供滤波与分类，电压未标定。',
    'file': '日志快速回放（按顺序处理，不是实时速度）：来源以文件内声明为准，不能证明板卡已连接。',
    'serial': '板卡 → 电脑只接收：来源与检测器由发送端声明，本机不运行QRS/CNN，也不向板卡发命令。',
}


REASON_TEXT = {
    'stopped_by_user': '已手动停止', 'completed': '数据已全部处理完', 'window_closed': '窗口关闭',
    'no_waveform_data': '没有ECG-UART-1波形帧（smoke自检文本日志不是波形流，不代表smoke失败）',
    'start_error': '启动失败', 'input_or_record_error': '输入或记录出错', 'preloaded': '预载数据',
}


QUIET_SECONDS = 2.0  # 超过该时长无新字节只提示“暂无新数据”，不据此判定断连。


def describe_reason(reason):
    parts = []
    for piece in reason.split('; '):
        base, _, detail = piece.partition(': ')
        parts.append(REASON_TEXT.get(base, base) + ('：' + detail if detail else ''))
    return '；'.join(parts)


def is_error_reason(reason):
    return reason.split(': ', 1)[0] in ('start_error', 'input_or_record_error') or 'close_error' in reason


def enable_windows_dpi_awareness():
    """在创建Tk前声明DPI感知，避免Windows位图放大导致发虚；失败时保持系统默认。"""
    if os.name != 'nt':
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class Application:
    """界面分四层：状态/来源 → 操作 → 关键数值 → 波形；事件表与诊断详情放在底部分页。"""
    def __init__(self, root, monitor=None):
        import tkinter as tk
        from tkinter import ttk, font as tkfont
        self.tk = tk; self.root = root
        self.monitor = monitor or Monitor()
        self.running = False; self.input_file = None; self.frames = None; self.pending = None
        self.output = None; self.kind = None; self.serial_input = None
        self.state = 'idle'; self.stop_reason = None; self._detail_cache = None
        self._sample_count_seen = 0; self._sample_progress_at = None
        root.title('ECG PC监视器')
        # 96像素/英寸为1.0；DPI感知时Windows 150%缩放约为1.5。只用于像素边距，字号由Tk按点数自动缩放。
        self.ui_scale = max(root.winfo_fpixels('1i') / 96, 1.0)
        width = min(int(1180 * self.ui_scale), int(root.winfo_screenwidth() * .92))
        height = min(int(780 * self.ui_scale), int(root.winfo_screenheight() * .88))
        root.geometry(f'{width}x{height}')
        root.minsize(min(int(760 * self.ui_scale), width), min(int(560 * self.ui_scale), height))

        base = tkfont.nametofont('TkDefaultFont')
        # Tk字号正数为点、负数为像素；保持原单位，只按增量放大，避免Linux/Windows默认字体差异。
        raw_size = base.cget('size') or 10
        sign = -1 if raw_size < 0 else 1; size = abs(raw_size)
        sized = lambda delta: sign * max(size + delta, 8)
        self.fonts = {'body': base.copy(), 'small': base.copy(), 'title': base.copy(),
                      'value': base.copy(), 'canvas': base.copy(), 'guide': base.copy()}
        self.fonts['small'].configure(size=sized(-1))
        self.fonts['title'].configure(size=sized(3), weight='bold')
        self.fonts['value'].configure(size=sized(6), weight='bold')
        self.fonts['guide'].configure(size=sized(2))
        style = ttk.Style(root)
        style.configure('Hint.TLabel', foreground='#4a5560')
        style.configure('Card.TFrame', relief='groove', borderwidth=1)
        style.configure('CardTitle.TLabel', foreground='#5f6b76', font=self.fonts['small'])
        style.configure('CardValue.TLabel', font=self.fonts['value'])
        style.configure('CardNote.TLabel', foreground='#8a6d00', font=self.fonts['small'])
        style.configure('Error.TLabel', foreground='#b3261e')
        # Windows开启DPI感知后Treeview行高不随字号自动增加，按实际行距设置，避免文字被裁切。
        style.configure('Treeview', rowheight=self.fonts['body'].metrics('linespace') + int(6 * self.ui_scale))
        pad = int(10 * self.ui_scale); gap = int(6 * self.ui_scale)
        self.pad = pad
        root.columnconfigure(0, weight=1)

        # 第1层：程序状态与数据来源说明。
        top = ttk.Frame(root); top.grid(row=0, column=0, sticky='ew', padx=pad, pady=(pad, gap))
        top.columnconfigure(2, weight=1)
        ttk.Label(top, text='ECG PC监视器', font=self.fonts['title']).grid(row=0, column=0, sticky='w')
        self.badge = tk.Label(top, text='', fg='white', padx=8, pady=2, font=self.fonts['body'])
        self.badge.grid(row=0, column=1, sticky='w', padx=(pad, 0))
        self.source_text = tk.StringVar()
        self.source_label = ttk.Label(top, textvariable=self.source_text, style='Hint.TLabel')
        self.source_label.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(gap // 2, 0))

        # 第2层：操作。离线来源与串口分两行，避免窄窗口挤压。
        controls = ttk.Frame(root); controls.grid(row=1, column=0, sticky='ew', padx=pad)
        controls.columnconfigure(1, weight=1)
        offline = ttk.LabelFrame(controls, text='离线来源', padding=gap)
        offline.grid(row=0, column=0, sticky='w')
        self.demo_button = ttk.Button(offline, text='开始演示', command=self.start_demo)
        self.demo_button.pack(side='left', padx=(0, gap))
        self.file_button = ttk.Button(offline, text='打开日志回放…', command=self.open_file)
        self.file_button.pack(side='left')
        serial = ttk.LabelFrame(controls, text='板卡串口（只接收）', padding=gap)
        serial.grid(row=0, column=1, sticky='w', padx=(pad, 0))
        ttk.Label(serial, text='端口').pack(side='left')
        self.port_text = tk.StringVar(value='')
        self.port_entry = ttk.Combobox(serial, textvariable=self.port_text, width=8, state='readonly')
        self.port_entry.pack(side='left', padx=gap)
        self.port_refresh = ttk.Button(serial, text='识别端口', command=self.refresh_ports)
        self.port_refresh.pack(side='left', padx=(0, gap))
        ttk.Label(serial, text='115200 · 8N1 · 无流控', style='Hint.TLabel').pack(side='left', padx=(0, gap))
        self.serial_button = ttk.Button(serial, text='连接并记录', command=self.open_serial)
        self.serial_button.pack(side='left')
        session = ttk.LabelFrame(controls, text='本次记录', padding=gap)
        session.grid(row=0, column=2, sticky='e', padx=(pad, 0))
        self.stop_button = ttk.Button(session, text='停止并保存', command=self.stop)
        self.stop_button.pack(side='left', padx=(0, gap))
        self.export_button = ttk.Button(session, text='导出SVG…', command=self.export)
        self.export_button.pack(side='left')
        self.controls = controls; self.control_groups = (offline, serial, session)

        capture_bar = ttk.Frame(controls)
        capture_bar.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(gap, 0))
        self.capture_button = ttk.Button(capture_bar, text='采集 / 厂商CSV…', command=self.open_capture)
        self.capture_button.pack(side='left')
        ttk.Label(capture_bar, text='蓝牙/CSV双通道原码', style='Hint.TLabel').pack(side='left', padx=gap)
        self.capture_panel = None
        self.bridge_button = ttk.Button(capture_bar, text='送样 / 双向中转…', command=self.open_bridge)
        self.bridge_button.pack(side='left', padx=gap)
        self.bridge_panel = None
        self.port_inventory = []; self.port_device = None; self.port_remembered = False
        self.port_hint = tk.StringVar()
        self.port_hint_label = ttk.Label(controls, textvariable=self.port_hint, style='Hint.TLabel', wraplength=700)
        self.port_hint_label.grid(row=3, column=0, columnspan=3, sticky='ew')
        self.refresh_ports()

        # 第3层：关键数值卡片；停止后标“历史”，未知值显示“未知/未提供”。
        cards = ttk.Frame(root); cards.grid(row=2, column=0, sticky='ew', padx=pad, pady=gap)
        self.card_vars = {}; self.card_notes = {}
        for col, (key, title) in enumerate([('hr', '心率 (次/分)'), ('rr', 'RR间期'), ('cls', '心拍类别'),
                                            ('samples', '累计样本'), ('events', '事件数')]):
            cards.columnconfigure(col, weight=1, uniform='card')
            card = ttk.Frame(cards, style='Card.TFrame', padding=(pad, gap))
            card.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else gap, 0))
            ttk.Label(card, text=title, style='CardTitle.TLabel').pack(anchor='w')
            self.card_vars[key] = tk.StringVar(value='—')
            ttk.Label(card, textvariable=self.card_vars[key], style='CardValue.TLabel').pack(anchor='w')
            self.card_notes[key] = tk.StringVar(value='')
            ttk.Label(card, textvariable=self.card_notes[key], style='CardNote.TLabel').pack(anchor='w')

        # 第4层：波形，占剩余空间的主要部分。
        self.canvas = tk.Canvas(root, background='#101820', highlightthickness=0,
                                height=int(260 * self.ui_scale))
        self.canvas.grid(row=3, column=0, sticky='nsew', padx=pad)
        root.rowconfigure(3, weight=3)
        self.canvas.bind('<Configure>', lambda _: self.draw())

        # 底部分页：事件表 / 诊断详情（协议、计数、记录位置）。
        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=4, column=0, sticky='nsew', padx=pad, pady=(gap, 0))
        root.rowconfigure(4, weight=1)
        events = ttk.Frame(self.notebook); events.columnconfigure(0, weight=1); events.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(events, columns=('evt', 'pos', 'rr', 'hr', 'cls'), show='headings', height=5)
        for name, title in [('evt', '事件号'), ('pos', '位置（样本号）'), ('rr', 'RR（样本数）'), ('hr', '心率'), ('cls', '类别')]:
            self.table.heading(name, text=title); self.table.column(name, width=int(110 * self.ui_scale), anchor='center', stretch=True)
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(events, orient='vertical', command=self.table.yview)
        scroll.grid(row=0, column=1, sticky='ns'); self.table.configure(yscrollcommand=scroll.set)
        self.notebook.add(events, text='最近事件')
        details = ttk.Frame(self.notebook); details.columnconfigure(0, weight=1); details.rowconfigure(0, weight=1)
        self.detail = tk.Text(details, height=7, wrap='word', font=self.fonts['small'], relief='flat',
                              background=root.cget('background'), state='disabled')
        self.detail.grid(row=0, column=0, sticky='nsew', padx=gap, pady=gap)
        detail_scroll = ttk.Scrollbar(details, orient='vertical', command=self.detail.yview)
        detail_scroll.grid(row=0, column=1, sticky='ns'); self.detail.configure(yscrollcommand=detail_scroll.set)
        self.notebook.add(details, text='诊断详情')

        # 状态栏：记录位置、停止原因或错误。
        self.message_text = tk.StringVar(value=f'每次开始都会在 {DEFAULT_OUTPUT.relative_to(ROOT).as_posix()} 下新建目录记录，不覆盖旧记录。')
        self.message_label = ttk.Label(root, textvariable=self.message_text, style='Hint.TLabel')
        self.message_label.grid(row=5, column=0, sticky='ew', padx=pad, pady=(gap, pad))

        root.bind('<Configure>', self._on_resize, add='+')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.draw()
        root.after(40, self.tick)

    def _on_resize(self, event):
        if event.widget is not self.root:
            return
        # 说明文字随窗口宽度换行，不再固定1050像素。
        wrap = max(event.width - 2 * self.pad, 200)
        self.source_label.configure(wraplength=wrap); self.message_label.configure(wraplength=wrap)
        self.port_hint_label.configure(wraplength=wrap)
        # 窄窗口时把“本次记录”组换到下一行，避免按钮被裁切。
        session = self.control_groups[2]
        need = sum(g.winfo_reqwidth() for g in self.control_groups) + 4 * self.pad
        if event.width < need:
            session.grid_configure(row=1, column=0, columnspan=2, sticky='w', padx=0, pady=(self.pad // 2, 0))
        else:
            session.grid_configure(row=0, column=2, columnspan=1, sticky='e', padx=(self.pad, 0), pady=0)

    # ---------- 状态 ----------
    def compute_state(self):
        if not self.running:
            if self.stop_reason is None:
                return 'idle'
            return 'error' if is_error_reason(self.stop_reason) else 'stopped'
        if self.kind == 'demo':
            return 'demo'
        if self.kind == 'file':
            return 'replay'
        last = self.serial_input.last_data if self.serial_input else None
        if self.monitor.header is None or last is None:
            return 'serial_wait'
        return 'serial_quiet' if time.monotonic() - last > QUIET_SECONDS else 'serial_live'

    def wait_hint(self):
        """串口等待阶段的用户说明；没有H时不显示单位/会话，也不画猜测波形。"""
        received = self.monitor.decoder.counts['bytes']
        if received == 0:
            return '串口已打开，尚未收到任何字节。确认板端程序已运行、端口号正确且其他串口终端已关闭。'
        return (f'已收到 {received} 字节（原文已写入记录），但尚未收到合法H报文（会话头）。'
                '程序不猜测单位或会话；需等待板端发送ECG-UART-1会话头后才能显示波形。')

    # ---------- 操作 ----------
    def refresh_ports(self):
        if self.running:
            return
        previous = next((p for p in self.port_inventory if p['port'] == self.port_text.get()), None)
        self.port_inventory, warnings = enumerate_ports()
        self.port_entry.configure(values=[p['port'] for p in self.port_inventory])
        self.port_text.set(select_port(self.port_inventory, previous, identity=remembered_identity('zynq')))
        selected = next((p for p in self.port_inventory if p['port'] == self.port_text.get()), None)
        self.port_hint.set((f"候选 {selected['port']}：{selected['label']}（连接后核对会话）" if selected else
                           '未唯一识别板卡；请选择实际USB_UART端口') + ('；'+ '；'.join(warnings[:1]) if warnings else ''))

    def open_bridge(self):
        from .bridge import BridgePanel
        if self.bridge_panel is not None:
            self.bridge_panel.window.lift(); return
        if self.capture_panel is not None:
            self.capture_panel.window.lift(); return
        self.stop()
        self.bridge_panel = BridgePanel(self.root, on_closed=self._bridge_closed)
        self.serial_button.configure(state='disabled')
        self.capture_button.configure(state='disabled')

    def _bridge_closed(self):
        self.bridge_panel = None
        self.serial_button.configure(state='normal'); self.capture_button.configure(state='normal')

    def open_capture(self):
        from .capture import CapturePanel
        if self.capture_panel is not None:
            self.capture_panel.window.lift()
            return
        self.stop()
        self.capture_panel = CapturePanel(self.root, excluded_port=self.port_text.get().strip(),
                                          on_closed=self._capture_closed)
        self.serial_button.configure(state='disabled')
        self.bridge_button.configure(state='disabled')

    def _capture_closed(self):
        self.capture_panel = None
        self.serial_button.configure(state='normal')
        self.bridge_button.configure(state='normal')

    def start_demo(self):
        self.start('demo')

    def open_serial(self):
        from tkinter import messagebox
        try:
            port = self.port_text.get().strip()
            previous = next((p for p in self.port_inventory if p['port'] == port), None)
            self.port_device = validate_port(port, previous, enumerate_ports()[0])
            self.port_remembered = False
        except ValueError as error:
            messagebox.showerror('端口需要重新选择', str(error)); return
        self.start('serial', self.port_text.get().strip())

    def open_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title='选择ECG-UART-1原始行日志', filetypes=[('日志', '*.log *.txt'), ('全部文件', '*')])
        if path:
            self.start('file', Path(path))

    def start(self, kind, path=None):
        from tkinter import messagebox
        self.stop()
        self.kind = kind; self.stop_reason = None
        self.monitor = Monitor()  # 新来源不沿用上次会话的单位/数值；记录器创建失败时也保持空白。
        try:
            self.output = new_directory()
            recorder = Recorder(self.output)
            self.monitor = Monitor(recorder)
            if kind == 'demo':
                self.monitor.input_info = {'kind': 'demo'}
                self.frames = iter(demo_frames(60, 360, None, 'demo-' + uuid.uuid4().hex[:8]))
                self.pending = next(self.frames); self.started = time.monotonic()
            elif kind == 'serial':
                self.serial_input = SerialCapture(self.monitor, path)
            else:
                self.monitor.input_info = {'kind': 'replay', 'path': str(path)}
                self.input_file = path.open('rb')
            self.running = True
            self.message_text.set('正在记录：' + str(self.output))
            self.draw()
        except (OSError, ValueError) as error:
            self.running = True  # 让stop按统一流程关闭并写入失败原因。
            self.stop('start_error: ' + str(error))
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
                elif self.kind == 'serial':
                    self.serial_input.poll()
                    if self.monitor.header is not None and not self.port_remembered:
                        self.port_remembered = True
                        try:
                            remember_identity('zynq', self.port_device or {})
                        except OSError as error:
                            self.port_hint.set('接收正常，但USB身份记忆保存失败：'+str(error))
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
        if self.serial_input:
            try:
                self.serial_input.close()
            except OSError as error:
                reason += '; close_error: ' + str(error)
            self.serial_input = None
        if self.input_file:
            self.input_file.close(); self.input_file = None
        if not was_running:
            return
        self.stop_reason = reason
        text = describe_reason(reason)
        if self.monitor.recorder and not self.monitor.recorder.closed:
            try:
                self.monitor.finish(reason)
                text += f'。记录已保存：{self.output}'
            except OSError as error:
                self.stop_reason = 'input_or_record_error: ' + str(error)
                text = '记录关闭失败（磁盘/权限），已有文件保留：' + str(error)
        self.message_text.set(text)
        self.draw()

    def export(self):
        from tkinter import filedialog, messagebox
        path = filedialog.asksaveasfilename(title='保存当前SVG（不覆盖已存在文件）', defaultextension='.svg', filetypes=[('SVG', '*.svg')])
        if path:
            try:
                save_svg(self.monitor, path)
            except OSError as error:
                messagebox.showerror('导出失败', str(error))

    # ---------- 显示 ----------
    def class_text(self, value):
        h = self.monitor.header
        if h is None or not h.caps & CLASS:  # 未声明时是“未提供”，不是正常。
            return '未提供'
        return '未知' if value == '?' else value

    def draw(self):
        self.state = self.compute_state()
        label, color = STATE_STYLE[self.state]
        self.badge.configure(text=label, bg=color)
        style = 'Error.TLabel' if self.state == 'error' else 'Hint.TLabel'
        self.message_label.configure(style=style)
        h = self.monitor.header
        hint = SOURCE_HINT[self.kind]
        if h is not None and self.kind == 'file':
            hint += f' 文件声明来源：{h.source}，检测器：{h.detector}。'
        self.source_text.set(hint)
        self._draw_canvas()
        self._update_cards()
        self._update_table()
        self._update_details()

    def _draw_canvas(self):
        canvas = self.canvas; canvas.delete('all')
        # 按实际Canvas尺寸绘图；未完成布局时用请求尺寸，不再设固定900×330下限，避免画出界。
        width = canvas.winfo_width(); height = canvas.winfo_height()
        if width < 2 or height < 2:
            width = canvas.winfo_reqwidth(); height = canvas.winfo_reqheight()
        s = self.ui_scale; font = self.fonts['canvas']
        line_h = font.metrics('linespace')
        margins = (int(64 * s), int(16 * s), line_h + int(14 * s), line_h + int(16 * s))
        left, right = margins[0], max(width - margins[1], margins[0] + 1)
        top, bottom = margins[2], max(height - margins[3], margins[2] + 1)
        self.plot_size = (width, height)  # 本次绘图实际采用的尺寸，供越界检查使用。
        g = plot_geometry(self.monitor, width, height, margins)
        for i in range(0, 6):
            y = top + i * (bottom - top) / 5
            canvas.create_line(left, y, right, y, fill='#283744')
        if not (g['raw'] or g['filt']):
            self._draw_guide(width, height)
            return
        for name, color in [('raw', '#58d6a6'), ('filt', '#70baff')]:
            for segment in g[name]:
                canvas.create_line(*[v for point in segment for v in point], fill=color, width=max(1.4 * s, 1), tags='wave')
        for x, seq in g['events']:
            canvas.create_line(x, top, x, bottom, fill='#ffcd70', dash=(4, 4), tags='event')
            # 靠近右边缘时把事件号放到竖线左侧，避免文字画出Canvas。
            near_right = x > right - font.measure(str(seq)) - 8
            canvas.create_text(x - 4 if near_right else x + 4, top + 2, text=str(seq), fill='#ffcd70',
                               anchor='ne' if near_right else 'nw', font=font)
        h = self.monitor.header
        filt = '蓝=滤波' if h.caps & FILT else '滤波：未提供'
        marker = '黄虚线=演示标记' if h.detector == 'SYNTH-MARKERS' else '黄虚线=检测器候选'
        legend = f'绿=原始  {filt}  {marker}  |  纵轴：{g["unit"]}'
        canvas.create_text(int(12 * s), int(6 * s), text=legend, fill='#dfe6ec', anchor='nw', font=font,
                           width=max(width - int(24 * s), 1))
        for value, y, anchor in [(g['high'], top, 'ne'), (g['low'], bottom, 'se')]:
            text = f'{value:.2f}' if h.scale else f'{value:.0f}'
            canvas.create_text(left - 6, y, text=text, fill='#9fb0bf', anchor=anchor, font=font)
        unit = 's' if h.fs else ''
        axis = f"{g['first']:.2f}{unit} → {g['last']:.2f}{unit}（{g['time_unit']}，非串口到达时间）"
        if not self.running and self.stop_reason is not None:
            axis += '  · 历史数据'
        canvas.create_text(left, height - int(6 * s), text=axis, fill='#dfe6ec', anchor='sw', font=font,
                           width=max(right - left, 1))

    def _draw_guide(self, width, height):
        """空白绘图区给出下一步操作，不显示无意义的坐标范围。"""
        if self.state == 'idle':
            title = '尚无数据'
            body = '点「开始演示」查看合成波形；或「打开日志回放…」选择raw.log；\n连接板卡时填写COM端口后点「连接并记录」。'
        elif self.state == 'serial_wait':
            title = '等待板端数据'
            body = self.wait_hint()
        elif self.running:
            title = '正在读取…'
            body = '尚未得到可绘制的波形样本。'
        else:
            title = '本次没有可显示的波形'
            body = describe_reason(self.stop_reason or '') + '\n原始数据仍保存在记录目录，可在“诊断详情”查看计数。'
        wrap = max(width - int(80 * self.ui_scale), 120)
        canvas = self.canvas
        canvas.create_text(width / 2, height / 2 - self.fonts['guide'].metrics('linespace'), text=title,
                           fill='#dfe6ec', font=self.fonts['guide'], anchor='s', tags='guide')
        canvas.create_text(width / 2, height / 2 - self.fonts['guide'].metrics('linespace') + 8, text=body,
                           fill='#9fb0bf', font=self.fonts['body'], anchor='n', justify='center', width=wrap, tags='guide')

    def _update_cards(self):
        m = self.monitor; h = m.header
        history = not self.running and self.stop_reason is not None and m.counts['samples'] > 0
        note = '历史数据（已停止）' if history else ''
        now=time.monotonic();count=m.counts['samples']
        if count!=self._sample_count_seen:
            self._sample_count_seen=count;self._sample_progress_at=now if count else None
        if self.running and self.kind=='serial' and self._sample_progress_at is not None and now-self._sample_progress_at>QUIET_SECONDS:
            note='历史数值（暂无新波形）'

        if h is None:
            values = {'hr': '—', 'rr': '—', 'cls': '—'}
            note_unknown = '等待会话头' if self.state == 'serial_wait' else ''
        else:
            values = {'hr': '未知' if m.hr is None else f'{m.hr:.1f}',
                      'rr': '未知' if m.rr_ms is None else f'{m.rr_ms:.0f} ms',
                      'cls': self.class_text(m.cls)}
            note_unknown = ''
        values['samples'] = str(m.counts['samples']); values['events'] = str(m.counts['events'])
        for key, value in values.items():
            self.card_vars[key].set(value)
            self.card_notes[key].set(note or (note_unknown if key in ('hr', 'rr', 'cls') else ''))
        if h is not None and h.detector == 'SYNTH-MARKERS' and not note:
            self.card_notes['hr'].set('来自演示标记间隔')

    def _update_table(self):
        h = self.monitor.header
        title = '标记位置（演示）' if h is not None and h.detector == 'SYNTH-MARKERS' else '候选位置（样本号）'
        self.table.heading('pos', text=title)
        self.table.delete(*self.table.get_children())
        for event in list(self.monitor.events)[-50:][::-1]:
            hr = '未知' if event.hr is None else f'{event.hr:.1f}'
            rr = '—（首个）' if event.rr == 0 else event.rr
            self.table.insert('', 'end', values=(event.seq, event.pos, rr, hr, self.class_text(event.cls)))

    def detail_lines(self):
        m = self.monitor; h = m.header; c = m.counts; p = m.decoder.counts; s = m.status
        unknown = lambda v: '未提供' if v is None else str(v)
        lines = ['【会话】']
        if h is None:
            lines.append('尚未收到合法H报文（会话头）：不显示单位、采样率和会话。' +
                         (f'已收原始字节 {p["bytes"]}，已保存。' if self.running and p['bytes'] else ''))
        else:
            lines += [f'session {h.session} · firmware {h.firmware} · 来源声明 {h.source} · 检测器 {h.detector}',
                      f'fs {unknown(h.fs)} Hz · scale {unknown(h.scale)} 码值/mV · caps 0x{h.caps:X}'
                      '（来源为发送端声明，不是本机认证的硬件证据）']
        lines += ['', '【接收与缺口】',
                  f'样本 {c["samples"]} · 事件 {c["events"]} · 会话数 {c["sessions"]}',
                  f'波形序号缺口 {c["wave_gap"]} · 事件序号缺口 {c["event_gap"]}（只统计首帧之后，不推断首帧前）',
                  f'板端统计：FIFO丢事件 {unknown(None if s is None else s.event_drop)} · 源丢样 {unknown(None if s is None else s.source_drop)}'
                  f' · 发送丢弃 {unknown(None if s is None else s.tx_drop)}',
                  '', '【协议解析】',
                  f'坏行 {p["invalid"]} · 超长 {p["overlong"]} · 非协议行 {p["unknown"]} · 末尾不完整 {p["truncated"]} · 重复H {p["duplicate_header"]}',
                  '最近解析错误：' + (m.decoder.last_error or '无')]
        info = m.input_info
        if info.get('kind') == 'serial':
            last = info.get('last_data_after_start_s')
            lines += ['', '【串口】', f'{info.get("port")} · {info.get("baud")} · {info.get("format")} · 无流控 · 只接收、不发命令',
                      f'已收字节 {info.get("received_bytes")} · ' +
                      ('尚未收到字节' if last is None else f'最后字节在打开后 {last:.1f}s 到达（接收时间，不是采样时间）'),
                      '错误：' + (info.get('error') or '无')]
        elif info.get('kind') == 'replay':
            lines += ['', '【回放文件】', str(info.get('path'))]
        if m.logs:
            lines += ['', '【板端日志（最近）】'] + list(m.logs)[-5:]
        lines += ['', '【记录】', str(self.output) if self.output else '尚未开始记录']
        return lines

    def _update_details(self):
        text = '\n'.join(self.detail_lines())
        if text == self._detail_cache:
            return
        self._detail_cache = text
        position = self.detail.yview()[0]
        self.detail.configure(state='normal'); self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', text); self.detail.configure(state='disabled')
        self.detail.yview_moveto(position)

    def close(self):
        if getattr(self, 'bridge_panel', None) is not None:
            self.stop('window_closed')
            self.bridge_panel.shutdown(self.root.destroy)
            return
        self.stop('window_closed')
        if getattr(self, 'capture_panel', None) is not None:
            self.capture_panel.shutdown(self.root.destroy)
        else:
            self.root.destroy()


def ui_self_test(args):
    import tkinter as tk
    output = args.output_dir or new_directory()
    monitor = Monitor(Recorder(output, args.max_bytes))
    for _, data in demo_frames(3.01, session='ui-self-test'):
        monitor.feed(data)
    monitor.finish('ui_self_test')
    root = tk.Tk(); root.withdraw()
    try:
        idle = Application(root)
        root.update_idletasks(); idle.draw()
        assert idle.state == 'idle' and idle.canvas.find_withtag('guide') and not idle.canvas.find_withtag('wave')
        assert idle.card_vars['hr'].get() == '—' and '尚无数据' in str(idle.canvas.itemcget(idle.canvas.find_withtag('guide')[0], 'text'))
    finally:
        root.destroy()
    root = tk.Tk(); root.withdraw()
    try:
        app = Application(root, monitor)
        app.stop_reason = 'preloaded'
        app.canvas.configure(width=1000, height=360)  # 隐藏窗口未映射时按该请求尺寸绘图
        root.update_idletasks(); app.draw()
        assert app.canvas.find_withtag('wave') and app.canvas.find_withtag('event')
        assert app.state == 'stopped' and app.card_vars['cls'].get() == '未提供'
        assert '历史' in app.card_notes['hr'].get()
        assert len(app.table.get_children()) == len(monitor.events)
        bbox = app.canvas.bbox('all')
        width, height = app.plot_size
        assert bbox is None or (bbox[0] >= -2 and bbox[1] >= -2 and bbox[2] <= width + 2 and bbox[3] <= height + 2), (bbox, width, height)
        result = {'passed': True, 'tk': root.tk.call('info', 'patchlevel'), 'ui_scale': app.ui_scale,
                  'samples': monitor.counts['samples'], 'canvas_wave_items': len(app.canvas.find_withtag('wave')),
                  'canvas_event_items': len(app.canvas.find_withtag('event')), 'canvas_size': [width, height],
                  'canvas_bbox': list(bbox) if bbox else None,
                  'scope': 'hidden-window construction/states; not manual visual review or serial test'}
        save_svg(monitor, Path(output) / 'waveform.svg')
        (Path(output) / 'ui_check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output_dir': str(output), **result}, ensure_ascii=False))
    finally:
        root.destroy()
    return 0

