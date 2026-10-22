"""现有监视器内的采集子窗口：厂商CSV/蓝牙双通道；不运行QRS/CNN或向Zynq送样。"""
from datetime import datetime
from pathlib import Path
import time
import uuid

from ecg_capture_core import CaptureWorker
from ecg_ports import enumerate_ports, candidate_port

from ecg_paths import ROOT
from .plot import trace_geometry, draw_trace as draw_trace_shared




class CapturePanel:
    def __init__(self, parent, *, excluded_port='', on_closed=lambda: None):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk; self.on_closed = on_closed; self.excluded_port = excluded_port
        self.window = tk.Toplevel(parent); self.window.title('ECG采集与厂商CSV回放')
        self.window.geometry(f'{min(1120, int(parent.winfo_screenwidth()*.9))}x{min(800, int(parent.winfo_screenheight()*.88))}')
        self.window.minsize(680, 520)
        self.window.columnconfigure(0, weight=1)
        self.worker = None; self.closing = False; self.shutdown_callback = None
        self.wrapped_labels = []
        self.port = tk.StringVar(); self.shift = tk.StringVar(value='8')
        self.view = tk.StringVar(value='原始码'); self.status = tk.StringVar(value='未开始')
        self.detail = tk.StringVar(value='CH2心电 / CH1呼吸；本窗口不计算心率或分类，不向Zynq送样。')
        self.identity = tk.StringVar(value='点击刷新枚举设备；候选提示不证明设备用途。')
        self.records = tk.StringVar(value='完整记录默认保存在 tmp/pc_capture_logs/ 的新目录，不覆盖历史。')
        self.help = tk.StringVar(value='请选择厂商RawData CSV，或连接采集侧USB蓝牙接收适配器。')
        title = ttk.Label(self.window, textvariable=self.status, wraplength=640, font=('Microsoft YaHei', 13, 'bold'))
        title.grid(row=0, column=0, sticky='ew', padx=10, pady=6)
        hint = ttk.Label(self.window, textvariable=self.help, wraplength=640)
        hint.grid(row=1, column=0, sticky='ew', padx=10)
        self.wrapped_labels.extend((title, hint))
        controls = ttk.Frame(self.window, padding=8); controls.grid(row=2, column=0, sticky='ew')
        self.csv_button = ttk.Button(controls, text='打开厂商CSV…', command=self.open_csv)
        self.csv_button.grid(row=0, column=0, sticky='w', padx=3)
        ttk.Label(controls, text='采集端口').grid(row=0, column=1)
        self.ports_box = ttk.Combobox(controls, textvariable=self.port, width=12, state='readonly')
        self.ports_box.grid(row=0, column=2, padx=3)
        self.ports_box.bind('<<ComboboxSelected>>', lambda _: self.show_identity())
        self.refresh_button = ttk.Button(controls, text='刷新', command=self.refresh_ports)
        self.refresh_button.grid(row=0, column=3, padx=3)
        self.serial_button = ttk.Button(controls, text='连接采集并记录', command=self.open_serial)
        self.serial_button.grid(row=0, column=4, padx=3)
        self.stop_button = ttk.Button(controls, text='停止并保存', command=self.stop)
        self.stop_button.grid(row=1, column=0, sticky='w', pady=6, padx=3)
        ttk.Label(controls, text='算法预览右移位数').grid(row=1, column=1, columnspan=2, sticky='w')
        self.shift_box = ttk.Spinbox(controls, from_=0, to=23, textvariable=self.shift, width=5)
        self.shift_box.grid(row=1, column=3)
        self.view_box = ttk.Combobox(controls, textvariable=self.view, values=('原始码', '厂商滤波'), state='readonly', width=14)
        self.view_box.grid(row=1, column=4)
        for row, value in ((3, self.identity), (4, self.detail)):
            label = ttk.Label(self.window, textvariable=value, wraplength=640)
            label.grid(row=row, column=0, sticky='ew', padx=10, pady=3)
            self.wrapped_labels.append(label)
        self.canvases = {}
        for row, channel in ((5, 'ecg'), (6, 'resp')):
            canvas = tk.Canvas(self.window, bg='#101820', highlightthickness=0, height=180)
            canvas.grid(row=row, column=0, sticky='nsew', padx=10, pady=3)
            self.window.rowconfigure(row, weight=1)
            self.canvases[channel] = canvas
        location = ttk.Label(self.window, textvariable=self.records, wraplength=640)
        location.grid(row=7, column=0, sticky='ew', padx=10, pady=6)
        self.wrapped_labels.append(location)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.bind('<Configure>', self.resize)
        self.inventory = []
        self.refresh_ports()
        self.window.after(40, self.tick)

    def resize(self, event):
        if event.widget is self.window:
            for label in self.wrapped_labels:
                label.configure(wraplength=max(event.width-20, 200))

    def refresh_ports(self):
        if self.worker and self.worker.is_alive():
            return
        previous = next((p for p in self.inventory if p['port'] == self.port.get()), None)
        self.inventory, warnings = enumerate_ports()
        self.ports_box.configure(values=[p['port'] for p in self.inventory])
        # 只有可用的同一USB实例才保留选择，不把重用的旧COM号当作原设备。
        matches = [p for p in self.inventory if previous and previous['device_id'] and p['device_id'] == previous['device_id']]
        selected = matches[0]['port'] if len(matches) == 1 else candidate_port(self.inventory, self.excluded_port)
        self.port.set(selected)
        self.show_identity()
        if warnings:
            self.identity.set(self.identity.get() + '；' + '；'.join(warnings[:2]))

    def show_identity(self):
        selected = next((p for p in self.inventory if p['port'] == self.port.get()), None)
        if selected:
            self.identity.set(f"{selected['port']} · {selected['label']} · {selected['device_id']}；请确认是采集适配器")
        else:
            self.identity.set('未唯一选定采集端口；从列表选择实际USB蓝牙接收器，避免选到Zynq。')

    def open_csv(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.window, title='选择厂商RawData波形CSV（不是HeatData）', filetypes=[('CSV', '*.csv')])
        if path:
            self.start('csv', path)

    def open_serial(self):
        from tkinter import messagebox
        if not self.port.get():
            messagebox.showerror('未选择采集端口', '请刷新并选择采集侧USB蓝牙接收适配器。', parent=self.window)
            return
        if self.excluded_port and self.port.get().upper() == self.excluded_port.upper():
            messagebox.showerror('端口冲突', '该端口已在主窗口填写为Zynq端口，请核实采集端口。', parent=self.window)
            return
        previous = next((p for p in self.inventory if p['port'] == self.port.get()), None)
        current, _ = enumerate_ports()
        match = next((p for p in current if p['port'] == self.port.get()), None)
        if match is None or (previous and previous['device_id'] and previous['device_id'] != match['device_id']):
            messagebox.showerror('设备发生变化', '端口已消失或USB身份变化，请刷新后重新选择。', parent=self.window)
            return
        self.start('serial', self.port.get())

    def start(self, kind, source):
        from tkinter import messagebox
        if self.closing or (self.worker and self.worker.is_alive()):
            return
        try:
            shift = int(self.shift.get())
            directory = ROOT/'tmp/pc_capture_logs'/(datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8])
            identity = next((p for p in self.inventory if p['port'] == source), {}) if kind == 'serial' else {}
            self.worker = CaptureWorker(kind, source, directory, shift=shift, device_info=identity)
            self.view.set('原始码')
            self.worker.start()
            if kind == 'csv':
                self.help.set('厂商CSV按500Hz逻辑时间回放；滤波列为厂商历史结果，不是Zynq计算。')
            else:
                self.help.set('按v2.1.2资料配置：34字节/四点/115200/8N1；未读取固件版本。起始三帧仅为候选对齐，无CRC/源序号，不能证明无误码或丢样。')
            self.records.set(str(directory))
        except (OSError, ValueError) as error:
            messagebox.showerror('无法开始', str(error), parent=self.window)

    def stop(self):
        if self.worker:
            self.worker.stop()

    def tick(self):
        active = self.worker is not None and self.worker.is_alive()
        for button in (self.csv_button, self.serial_button, self.refresh_button, self.shift_box):
            button.configure(state='disabled' if active or self.closing else 'normal')
        self.ports_box.configure(state='disabled' if active or self.closing else 'readonly')
        if self.worker:
            info, samples = self.worker.snapshot()
            if info['error']:
                status = '已停止 · 出错：' + info['error']
            elif not active:
                status = ('回放完成' if info['csv_complete'] else '已停止') + ' · 显示历史数据'
            elif info['total']:
                status = '厂商CSV回放中' if info['kind'] == 'csv' else '蓝牙采集接收中'
                if info['last_data'] and time.monotonic() - info['last_data'] > 2:
                    status += ' · 暂无新数据（未判定断连）'
            else:
                status = '正在等待波形 / 起始候选边界'
            self.status.set(status)
            self.detail.set(f"样本 {info['total']} · 收到 {info['received_bytes']} 字节 · 初始候选前缀 {info['initial_bytes_skipped']} 字节 · 尾部缓存 {info['pending_bytes']} 字节 · 右移 {info['shift']} · 削顶 {info['clipped']} · 源丢样未知；心率/类别未计算")
            for channel, canvas in self.canvases.items():
                self.draw_trace(canvas, samples, channel, active)
        else:
            for channel, canvas in self.canvases.items():
                self.draw_trace(canvas, (), channel, False)
        if self.closing and not active:
            callback = self.shutdown_callback
            self.window.destroy(); self.on_closed()
            if callback:
                callback()
            return
        self.window.after(40, self.tick)

    def draw_trace(self, canvas, samples, channel, active, title_override=None):
        draw_trace_shared(canvas, samples, channel, active,
                          filtered=self.view.get() == '厂商滤波', title_override=title_override)

    def close(self):
        self.closing = True; self.stop()

    def shutdown(self, callback):
        self.shutdown_callback = callback
        self.close()
