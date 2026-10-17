"""离线输入、会话计数、有限显示缓存与非覆盖记录；不运行检测或分类模型。"""
from collections import Counter, deque
from dataclasses import asdict
import csv
from html import escape
import io
import json
import math
from pathlib import Path

from ecg_uart import Header, Wave, Event, Telemetry, Log, Ack, Decoder, ProtocolError, MASK


class RecordingLimitError(OSError):
    pass


class Recorder:
    """原始与解码文件合计限额；最终summary单独写，达到限额时保留已有文件。"""
    SAMPLE_FIELDS = ['session', 'source', 'detector', 'fs', 'scale', 'seq', 'index', 'time_s', 'raw', 'filt', 'raw_mv', 'filt_mv']
    EVENT_FIELDS = ['session', 'evt', 'rpos', 'rr', 'hr', 'cls', 'conf']
    STATUS_FIELDS = ['session', 'hr', 'rr_ms', 'cls', 'flags', 'fs', 'event_drop', 'source_drop', 'tx_drop', 'uptime_ms']

    def __init__(self, directory, max_bytes=64 * 1024 * 1024):
        if max_bytes < 1024:
            raise ValueError('记录限额至少1024字节')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.max_bytes = max_bytes
        self.bytes_written = 0
        self.files = {}
        self.closed = False
        try:
            for name in ('raw.log', 'samples.csv', 'events.csv', 'status.csv', 'sessions.jsonl'):
                self.files[name] = (self.directory / name).open('xb')
            for name, fields in [('samples.csv', self.SAMPLE_FIELDS), ('events.csv', self.EVENT_FIELDS), ('status.csv', self.STATUS_FIELDS)]:
                self.row(name, fields)
        except Exception:
            for stream in self.files.values():
                stream.close()
            raise

    def write(self, name, data):
        if self.closed:
            raise OSError('记录已关闭')
        if self.bytes_written + len(data) > self.max_bytes:
            raise RecordingLimitError('达到原始/解码数据记录上限')
        self.files[name].write(data)
        self.files[name].flush()
        self.bytes_written += len(data)

    def row(self, name, values):
        text = io.StringIO(newline='')
        csv.writer(text, lineterminator='\n').writerow('' if v is None else v for v in values)
        self.write(name, text.getvalue().encode('utf-8'))

    def header(self, frame):
        self.write('sessions.jsonl', (json.dumps(asdict(frame), ensure_ascii=False) + '\n').encode('utf-8'))

    def close(self, summary):
        if self.closed:
            return
        self.closed = True
        close_errors = []
        for stream in self.files.values():
            try:
                stream.close()
            except OSError as error:
                close_errors.append(str(error))
        summary = dict(summary, data_bytes_written=self.bytes_written, data_limit_bytes=self.max_bytes, close_errors=close_errors)
        # 摘要不与数据共用额度，确保限额/失败原因仍可保存；磁盘全满时该写入也可能失败。
        with (self.directory / 'summary.json').open('x', encoding='utf-8') as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        if close_errors:
            raise OSError('记录文件关闭失败：' + '; '.join(close_errors))


class Monitor:
    def __init__(self, recorder=None, buffer_samples=4096):
        self.recorder = recorder
        self.decoder = Decoder(self.accept)
        self.header = None
        self.samples = deque(maxlen=buffer_samples)
        self.events = deque(maxlen=256)
        self.logs = deque(maxlen=20)
        self.counts = Counter()
        self.expected_wave = None
        self.expected_event = None
        self.next_index = None
        self.status = None
        self.hr = None
        self.rr_ms = None
        self.cls = '?'

    @staticmethod
    def forward_gap(seq, expected):
        if expected is None:
            return 0
        gap = (seq - expected) & MASK
        if gap >= 0x80000000:
            raise ProtocolError('重复/倒序，不能当作大段丢失或重启')
        return gap

    def accept(self, frame):
        if isinstance(frame, Header):
            if self.recorder:
                self.recorder.header(frame)
            self.header = frame
            self.samples.clear(); self.events.clear(); self.logs.clear()
            self.expected_wave = self.expected_event = self.next_index = None
            self.status = None; self.hr = self.rr_ms = None; self.cls = '?'
            self.counts['sessions'] += 1
        elif isinstance(frame, Wave):
            gap = self.forward_gap(frame.seq0, self.expected_wave)
            first = frame.seq0 if self.next_index is None else self.next_index + gap
            h = self.header
            for offset, (raw, filt) in enumerate(frame.pairs):
                seq = (frame.seq0 + offset) & MASK; index = first + offset
                time_s = None if h.fs is None else index / h.fs
                raw_mv = None if h.scale is None else raw / h.scale
                filt_mv = None if h.scale is None or filt is None else filt / h.scale
                if self.recorder:
                    self.recorder.row('samples.csv', [h.session, h.source, h.detector, h.fs, h.scale, seq, index, time_s, raw, filt, raw_mv, filt_mv])
                self.samples.append((seq, index, raw, filt))
                self.counts['samples'] += 1
            self.counts['wave_gap'] += gap
            self.expected_wave = (frame.seq0 + len(frame.pairs)) & MASK
            self.next_index = first + len(frame.pairs)
        elif isinstance(frame, Event):
            gap = self.forward_gap(frame.seq, self.expected_event)
            if self.recorder:
                self.recorder.row('events.csv', [self.header.session, frame.seq, frame.pos, frame.rr, frame.hr, frame.cls, frame.conf])
            self.counts['event_gap'] += gap; self.counts['events'] += 1
            self.expected_event = (frame.seq + 1) & MASK
            self.events.append(frame)
            self.hr = frame.hr; self.rr_ms = 1000 * frame.rr / self.header.fs if frame.rr and self.header.fs else None
            self.cls = frame.cls
        elif isinstance(frame, Telemetry):
            if self.recorder:
                self.recorder.row('status.csv', [self.header.session, frame.hr, frame.rr_ms, frame.cls, frame.flags,
                                               frame.fs, frame.event_drop, frame.source_drop, frame.tx_drop, frame.uptime_ms])
            self.status = frame; self.hr = frame.hr; self.rr_ms = frame.rr_ms; self.cls = frame.cls
        elif isinstance(frame, Log):
            self.logs.append(frame.level + ': ' + frame.text)
        elif isinstance(frame, Ack):
            self.logs.append(f'命令应答 {frame.command_id}: {frame.status}')

    def feed(self, data):
        if self.recorder:
            self.recorder.write('raw.log', data)
        self.decoder.feed(data)

    def finish(self, reason='completed'):
        self.decoder.finish()
        result = self.summary(reason)
        if self.recorder:
            self.recorder.close(result)
        return result

    def summary(self, reason='running'):
        return {'reason': reason, 'counts': dict(self.counts), 'protocol_counts': dict(self.decoder.counts),
                'last_error': self.decoder.last_error,
                'last_header': None if self.header is None else asdict(self.header),
                'scope': 'PC offline parser/demo/replay only; no serial, detector or CNN executed'}

    def visible_events(self):
        # 只按实际保留的样本序号匹配，不把串口到达时刻或猜测的回绕时间当事件位置。
        positions = {p[0]: p[1] for p in self.samples}
        return [(event, positions[event.pos]) for event in self.events if event.pos in positions]


def demo_frames(seconds=10, fs=360, scale=None, session='demo'):
    """数学合成源；事件为指定标记，不是QRS检测结果；滤波与分类未提供。"""
    if not 1 <= fs <= 10000 or not 0 < seconds <= 3600:
        raise ValueError('演示fs为1..10000，时长为0..3600秒')
    if scale is not None and not 1 <= scale <= MASK:
        raise ValueError('scale必须为正或未知')
    total = max(1, round(seconds * fs)); period = max(1, round(.8 * fs)); origin = round(.4 * fs)
    yield 0, f'H,ECG-UART-1,pc-demo-1,{session},SYNTH,SYNTH-MARKERS,{fs},{scale if scale else -1},0xD\n'.encode()
    yield 0, b'L,I,Synthetic demo only; no ADC/filter/QRS/CNN execution\n'
    event_seq = 0; last_mark = None; last_hr = None; rr_ms = None; last_status_second = -1
    for start in range(0, total, 8):
        n = min(8, total - start); values = []
        for index in range(start, start + n):
            distance = ((index - origin + period / 2) % period) - period / 2
            raw = round(250 * math.sin(index * .05) + 16000 * math.exp(-.5 * (distance / max(fs * .012, 1))**2))
            values += [str(raw), 'NA']
        at = (start + n) / fs
        yield at, (f'W,{start},{n},' + ','.join(values) + '\n').encode()
        for index in range(start, start + n):
            if index >= origin and (index - origin) % period == 0:
                event_seq += 1; rr = 0 if last_mark is None else index - last_mark; last_mark = index
                last_hr = 60 * fs / rr if rr else None; rr_ms = 1000 * rr / fs if rr else None
                hr = '-1' if last_hr is None else f'{last_hr:.1f}'
                yield at, f'E,{event_seq},{index},{rr},{hr},?,-1\n'.encode()
        second = int(at)
        if second != last_status_second:
            last_status_second = second
            hr = '-1' if last_hr is None else f'{last_hr:.1f}'
            rr = '-1' if rr_ms is None else f'{rr_ms:.1f}'
            # 没有真实FIFO或UART发送队列，相关统计必须未知，不能编造硬件零丢弃。
            yield at, f'T,{hr},{rr},?,NA,{fs},-1,0,-1,{round(at * 1000)}\n'.encode()


def plot_geometry(monitor, width=1000, height=360):
    samples = list(monitor.samples)
    if not samples:
        return {'raw': [], 'filt': [], 'events': [], 'unit': '未提供', 'time_unit': '样本序号'}
    h = monitor.header; left, right, top, bottom = 64, width - 20, 30, height - 42
    first, last = samples[0][1], samples[-1][1]; span = max(last - first, 1)
    values = [v / h.scale if h.scale else v for p in samples for v in (p[2], p[3]) if v is not None]
    low, high = min(values), max(values)
    margin = max((high - low) * .1, .01 if h.scale else 1)
    low -= margin; high += margin
    x = lambda index: left + (index - first) / span * (right - left)
    y = lambda value: bottom - ((value / h.scale if h.scale else value) - low) / (high - low) * (bottom - top)
    paths = {'raw': [], 'filt': []}
    for key, field in [('raw', 2), ('filt', 3)]:
        segment = []; previous = None
        for p in samples:
            if p[field] is None or (previous is not None and p[1] != previous + 1):
                if len(segment) > 1: paths[key].append(segment)
                segment = []
            if p[field] is not None: segment.append((x(p[1]), y(p[field])))
            previous = p[1]
        if len(segment) > 1: paths[key].append(segment)
    return {**paths, 'events': [(x(index), event.seq) for event, index in monitor.visible_events()],
            'unit': 'mV（声明换算）' if h.scale else '码值（未标定）',
            'time_unit': '逻辑采样秒' if h.fs else '样本序号',
            'first': first / h.fs if h.fs else first, 'last': last / h.fs if h.fs else last,
            'low': low, 'high': high}


def save_svg(monitor, path):
    path = Path(path)
    geometry = plot_geometry(monitor); h = monitor.header
    title = '无数据' if h is None else f'{h.source} / {h.detector} / session={h.session}'
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="400" viewBox="0 0 1000 400">',
             '<rect width="1000" height="400" fill="#101820"/>',
             f'<text x="20" y="20" fill="#eeeeee">{escape(title)}</text>']
    for key, color in [('raw', '#58d6a6'), ('filt', '#70baff')]:
        for segment in geometry[key]:
            points = ' '.join(f'{x:.2f},{y:.2f}' for x, y in segment)
            parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.3"/>')
    for x, seq in geometry['events']:
        parts.append(f'<line x1="{x:.2f}" x2="{x:.2f}" y1="30" y2="318" stroke="#ffcd70" stroke-dasharray="4 4"/>')
    footer = f"{geometry['unit']} | {geometry['time_unit']} | QRS候选/演示标记，不是疾病判断；滤波与分类未提供时不绘制"
    parts.append(f'<text x="20" y="385" fill="#eeeeee">{escape(footer)}</text></svg>')
    with path.open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(parts))
