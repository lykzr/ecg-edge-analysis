"""送样/双向中转视图：来源原码与Zynq返回结果分区，三段协议不混用。"""
from datetime import datetime
from pathlib import Path
import uuid

from ecg_bridge_worker import BridgeWorker
from ecg_capture_core import CaptureSample
from .plot import draw_trace, trace_geometry
from ecg_ports import enumerate_ports, select_port, validate_port, remembered_identity, remember_identity

from ecg_paths import ROOT


class BridgePanel:
    def __init__(self, parent, *, on_closed=lambda: None):
        import tkinter as tk
        from tkinter import ttk
        self.window = tk.Toplevel(parent); self.window.title('ECG送样与双向中转')
        self.window.geometry('1060x780'); self.window.minsize(760, 580)
        self.window.columnconfigure(0, weight=1)
        self.on_closed = on_closed; self.closing = False; self.shutdown_callback = None
        self.worker = None; self.inventory = []; self.remembered = False
        self.zynq = tk.StringVar(); self.source = tk.StringVar(); self.shift = tk.StringVar(value='8')
        self.limit = tk.StringVar(value='5000'); self.view = tk.StringVar(value='原始码')
        self.state = tk.StringVar(value='未开始；先在Vitis运行ecg_bridge，不能运行ecg_stream')
        self.details = tk.StringVar(value='源：未连接；Zynq：未连接。CSV用REPLAY，蓝牙用ADC；两端500Hz，未标定。')
        self.location = tk.StringVar(value='来源完整记录在capture/，板端结果在results/；不向Flash写入。')
        title = ttk.Label(self.window, textvariable=self.state, wraplength=1000)
        title.grid(row=0, column=0, sticky='ew', padx=10, pady=6)
        controls = ttk.Frame(self.window, padding=8); controls.grid(row=1, column=0, sticky='ew')
        ttk.Label(controls, text='Zynq USB_UART').grid(row=0, column=0)
        self.zynq_box = ttk.Combobox(controls, textvariable=self.zynq, state='readonly', width=10)
        self.zynq_box.grid(row=0, column=1)
        ttk.Label(controls, text='采集USB接收器').grid(row=0, column=2, padx=6)
        self.source_box = ttk.Combobox(controls, textvariable=self.source, state='readonly', width=10)
        self.source_box.grid(row=0, column=3)
        self.refresh_button = ttk.Button(controls, text='识别端口', command=self.refresh_ports)
        self.refresh_button.grid(row=0, column=4, padx=6)
        self.csv_button = ttk.Button(controls, text='厂商CSV → Zynq…', command=self.open_csv)
        self.csv_button.grid(row=1, column=0, columnspan=2, sticky='w', pady=8)
        self.serial_button = ttk.Button(controls, text='蓝牙采集 → Zynq', command=self.open_serial)
        self.serial_button.grid(row=1, column=2, columnspan=2, sticky='w')
        self.stop_button = ttk.Button(controls, text='停止并保存', command=self.stop)
        self.stop_button.grid(row=1, column=4)
        ttk.Label(controls, text='CH2右移').grid(row=2, column=0)
        self.shift_box = ttk.Spinbox(controls, from_=0, to=23, textvariable=self.shift, width=8)
        self.shift_box.grid(row=2, column=1)
        ttk.Label(controls, text='蓝牙本轮点数').grid(row=2, column=2)
        self.limit_box = ttk.Entry(controls, textvariable=self.limit, width=10); self.limit_box.grid(row=2, column=3)
        ttk.Label(controls, text='CSV送全文件；蓝牙默认5000点').grid(row=2, column=4, padx=6)
        self.port_detail = tk.StringVar()
        ports_label = ttk.Label(self.window, textvariable=self.port_detail, wraplength=1000)
        ports_label.grid(row=2, column=0, sticky='ew', padx=10)
        self.zynq_box.bind('<<ComboboxSelected>>', lambda _: self.show_ports())
        self.source_box.bind('<<ComboboxSelected>>', lambda _: self.show_ports())
        detail = ttk.Label(self.window, textvariable=self.details, wraplength=1000)
        detail.grid(row=3, column=0, sticky='ew', padx=10, pady=6)
        self.canvases = {}
        for row, name in ((4, 'source'), (5, 'result')):
            canvas = tk.Canvas(self.window, bg='#101820', highlightthickness=0, height=190)
            canvas.grid(row=row, column=0, sticky='nsew', padx=10, pady=3)
            self.window.rowconfigure(row, weight=1); self.canvases[name] = canvas
        self.events_text = tk.StringVar(value='尚无板端事件；电脑不运行QRS/CNN。')
        event_label = ttk.Label(self.window, textvariable=self.events_text, wraplength=1000)
        event_label.grid(row=6, column=0, sticky='ew', padx=10, pady=4)
        location = ttk.Label(self.window, textvariable=self.location, wraplength=1000)
        location.grid(row=7, column=0, sticky='ew', padx=10, pady=4)
        self.labels = [title, ports_label, detail, event_label, location]
        self.window.bind('<Configure>', self.resize)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh_ports(); self.window.after(40, self.tick)

    def resize(self, event):
        if event.widget is self.window:
            for label in self.labels:
                label.configure(wraplength=max(200, event.width-20))

    def refresh_ports(self):
        if self.worker and self.worker.is_alive(): return
        previous = {name: next((p for p in self.inventory if p['port'] == var.get()), None)
                    for name, var in (('zynq', self.zynq), ('source', self.source))}
        self.inventory, warnings = enumerate_ports()
        ports = [p['port'] for p in self.inventory]
        self.zynq_box.configure(values=ports); self.source_box.configure(values=ports)
        self.zynq.set(select_port(self.inventory, previous['zynq'], identity=remembered_identity('zynq')))
        self.source.set(select_port(self.inventory, previous['source'], excluded=self.zynq.get()))
        self.show_ports()
        if warnings: self.port_detail.set(self.port_detail.get()+'；'+'；'.join(warnings[:1]))

    def show_ports(self):
        values = []
        for name, var in (('Zynq', self.zynq), ('采集', self.source)):
            p = next((p for p in self.inventory if p['port'] == var.get()), None)
            values.append(name+'：'+(f"{p['port']} {p['label']} {p['device_id']}" if p else '未唯一选定，请手选'))
        self.port_detail.set('；'.join(values))

    def open_csv(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.window, title='选择厂商五列RawData CSV', filetypes=[('CSV', '*.csv')])
        if path: self.start('csv', path)

    def open_serial(self):
        self.start('serial', self.source.get())

    def start(self, kind, source):
        from tkinter import messagebox
        if self.closing or (self.worker and self.worker.is_alive()): return
        try:
            shift = int(self.shift.get())
            current, _ = enumerate_ports()
            old = lambda port: next((p for p in self.inventory if p['port'] == port), None)
            zynq_device = validate_port(self.zynq.get(), old(self.zynq.get()), current)
            source_device = validate_port(source, old(source), current, excluded=self.zynq.get()) if kind == 'serial' else {}
            limit = int(self.limit.get()) if kind == 'serial' else None
            directory = ROOT/'tmp/pc_bridge_logs'/(datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:8])
            self.worker = BridgeWorker(kind, source, self.zynq.get(), directory, shift=shift,
                                       sample_limit=limit, zynq_device=zynq_device, source_device=source_device)
            self.remembered = False
            self.worker.start(); self.location.set(str(directory))
        except (OSError, ValueError) as exc:
            messagebox.showerror('无法开始中转', str(exc), parent=self.window)

    def stop(self):
        if self.worker: self.worker.stop()

    def tick(self):
        active = self.worker is not None and self.worker.is_alive()
        for button in (self.csv_button, self.serial_button, self.refresh_button, self.shift_box, self.limit_box):
            button.configure(state='disabled' if active or self.closing else 'normal')
        for box in (self.zynq_box, self.source_box):
            box.configure(state='disabled' if active or self.closing else 'readonly')
        samples = (); result_samples = (); events = ()
        if self.worker:
            info, capture, samples, (result, events, header) = self.worker.snapshot()
            samples = tuple(CaptureSample(s.index, s.index/500, s.resp_raw, s.ecg_raw) for s in samples)
            running_text = {'starting': '准备中', 'connecting': '等待板端确认', 'running': '送样并接收结果', 'draining': '停止来源，正在收尾'}
            end_text = '完整运行结束' if info['reason'] == 'completed' else '已手动停止'
            self.state.set(('出错：'+info['error']) if info['error'] else
                           ('中转中 · '+running_text.get(info['state'], info['state']) if active else f'{end_text} · 显示历史数据'))
            self.details.set(f"源 {info['source']}：{info['source_status']}，已记录 {capture['total']} 点；Zynq：{info['result_status']}；上传 {info['source_samples']} / 确认 {info['confirmed']} / 回传 {info['echoed']}；削顶 {capture['clipped']}；源丢样未知。")
            result_samples = tuple(CaptureSample(index, index/500, 8388608, raw+8388608) for seq, index, raw, filt in result)
            if header and not self.remembered:
                self.remembered = True
                try: remember_identity('zynq', info['zynq_device'])
                except OSError as exc: self.location.set(str(self.worker.directory)+'；设备身份保存失败：'+str(exc))
            if events:
                e = events[-1]
                self.events_text.set(f"板端事件 {e.seq} · 位置 {e.pos}（样本号，0起点）· RR {e.rr}点 · 心率 {e.hr if e.hr is not None else '未知'} · 分类未提供。黄色竖线为返回事件，非电脑检测。")
            else: self.events_text.set('尚无板端事件；分类和滤波未提供，不能把无事件解释为正常心拍。')
        # 复用原码绘图几何；上下坐标单位分别标明，不把int16画成24位或mV。
        for name, values in (('source', samples), ('result', result_samples)):
            canvas = self.canvases[name]
            draw_trace(canvas, values, 'ecg', active, title_override=(
                '来源 CH2 · 有符号24位原码（未标定）' if name == 'source' else
                'Zynq返回 · 右移/饱和后的int16算法输入及事件（未标定）'))
            if name == 'result' and values:
                _, bounds = trace_geometry(values, 'ecg', False, canvas.winfo_width(), canvas.winfo_height())
                if bounds:
                    lo, hi, t0, t1, left, right, top, bottom = bounds
                    for e in events:
                        t = e.pos/500
                        if t0 <= t <= t1 and t1 > t0:
                            x = left+(t-t0)/(t1-t0)*(right-left)
                            canvas.create_line(x, top, x, bottom, fill='#ffc14d', dash=(3, 3))
        if self.closing and not active:
            self.window.destroy(); self.on_closed()
            if self.shutdown_callback: self.shutdown_callback()
            return
        self.window.after(40, self.tick)

    def close(self):
        self.closing = True; self.stop()

    def shutdown(self, callback):
        self.shutdown_callback = callback; self.close()
