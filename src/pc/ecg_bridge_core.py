"""电脑中转核心：源数据队列、部分写、一包在途及结果/确认分流。"""
from collections import deque
import re
import time

from ecg_bridge_protocol import ack, encode, samples
from ecg_uart import Header, Wave, Event, Telemetry, Log, parse_line
from ecg_metrics import StageMetrics


class BridgeClient:
    def __init__(self, port, monitor, session, source, *, clock=time.monotonic,
                 write_log=lambda name, data: None, capacity=4096, timeout=2, profile='legacy500'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', session) or source not in ('ADC', 'REPLAY', 'SYNTH'):
            raise ValueError('会话或来源错误')
        if capacity < 32 or not 0 < timeout <= 30:
            raise ValueError('队列/超时参数错误')
        self.port, self.monitor, self.session, self.source = port, monitor, session, source
        self.clock, self.log, self.capacity, self.timeout = clock, write_log, capacity, timeout
        if profile not in ('legacy500','runtime360','runtime500'):
            raise ValueError('未知板端合同')
        self.boot_seen=profile=='legacy500'
        self.boot_deadline=clock()+timeout
        self.profile=profile
        self.rate,self.scale,self.detectors={'legacy500':(500,None,('QRS-ORIG-60','QRS-AUTOPEAK-60')),'runtime360':(360,4096,('QRS26-ARM',)),'runtime500':(500,4096,('QRS26-500-ARM',))}[profile]
        self.ready_header=(b'H,ECG-UART-1,ps-runtime500-ready,boot,UNKNOWN,QRS26-500-ARM,500,4096,0xD\n' if profile=='runtime500' else b'H,ECG-UART-1,ps-runtime-ready,boot,UNKNOWN,QRS26-ARM,360,4096,0xD\n')
        self.queue = deque()
        self.pending = b''
        self.lines = bytearray()
        self.waiting = None
        self.inflight = ()
        self.deadline = 0
        self.last_batch = clock()
        self.confirmed = self.echoed = self.received = 0
        self.eof = self.done = self.end_seen = False
        self.started = False
        self.peak = 0
        self.event_next = 1
        self.event_pos = None
        self.last_wave_at = None
        self.metrics = StageMetrics()
        self.sent_at = None
        self.created_at = clock()

    def add(self, values):
        values = tuple(values)
        if self.eof or self.done:
            raise ValueError('源结束后不能追加样本')
        if any(type(x) is not int or not -32768 <= x <= 32767 for x in values):
            raise ValueError('只接收明确转换后的int16算法样本')
        if len(values) + len(self.queue) > self.capacity:
            raise BufferError('源输入队列已满，停止并保存；不静默丢样')
        if self.received + len(values) > 1800000:
            raise ValueError('单会话超过1800000点')
        self.queue.extend(values); self.received += len(values)
        self.peak = max(self.peak, len(self.queue))

    def finish_source(self):
        self.eof = True

    def _send(self, data, state):
        if self.waiting or self.pending:
            raise RuntimeError('违反一包在途约定')
        self.pending = data; self.waiting = state
        self.sent_at = self.clock()
        self.deadline = self.clock() + self.timeout

    def _line(self, line):
        if (self.profile in ('runtime360','runtime500') and not self.started and
            line==self.ready_header):
            self.boot_seen=True
            self.log('controls.log',line)
            return
        if line.startswith(b'A,'):
            self.log('controls.log', line)
            session, next_value, state, reason = ack(line)
            if state == 'ERROR':
                raise OSError(f'Zynq拒绝会话：{reason}，next={next_value}')
            if session != self.session or self.pending:
                raise ValueError('确认会话错误或输入尚未完整发出')
            expected_state = {'I': 'READY', 'D': 'ACCEPTED', 'F': 'DONE'}.get(self.waiting)
            expected_next = self.confirmed + (len(self.inflight) if self.waiting == 'D' else 0)
            if state != expected_state or next_value != expected_next:
                raise ValueError('确认状态/序号错误，禁止重复提交')
            if self.monitor.header is None:
                raise ValueError('READY之前缺少结果H')
            if self.waiting == 'D':
                if self.echoed != next_value:
                    raise ValueError('确认之前的回传波形不完整')
                self.confirmed = next_value; self.inflight = ()
            if self.waiting == 'F':
                if not self.end_seen or self.echoed != self.received:
                    raise ValueError('结束确认与完整结果不一致')
                self.done = True
            self.metrics.record({'I':'init_roundtrip','D':'batch_roundtrip','F':'finish_roundtrip'}[self.waiting],self.clock()-self.sent_at)
            if self.done:self.metrics.record('session_wall',self.clock()-self.created_at)
            self.waiting = None
            return
        frame = parse_line(line.decode('ascii').rstrip('\r\n'), self.monitor.header)
        if isinstance(frame, Header):
            if ((frame.session, frame.source, frame.fs, frame.scale, frame.caps) != (
                self.session, self.source, self.rate, self.scale, 0xD)
                or frame.detector not in self.detectors):
                raise ValueError('Zynq结果会话/来源/采样率/能力不匹配')
            if self.monitor.header is not None and frame != self.monitor.header:
                raise ValueError('会话中途变更元数据')
        elif isinstance(frame, Wave):
            if self.waiting != 'D' or frame.seq0 != self.echoed:
                raise ValueError('回传波形乱序或不属于当前在途批次')
            offset = self.echoed - self.confirmed
            actual = tuple(raw for raw, filt in frame.pairs)
            if actual != self.inflight[offset:offset + len(actual)] or any(filt is not None for raw, filt in frame.pairs):
                raise ValueError('回传样本与上传值不一致')
            self.echoed += len(actual)
            self.last_wave_at = self.clock()
        elif isinstance(frame, Event):
            if frame.pos >= self.confirmed + len(self.inflight):
                raise ValueError('事件位置超出已经发送的样本')
            expected_rr = 0 if self.event_pos is None else frame.pos - self.event_pos
            if frame.seq != self.event_next or frame.rr != expected_rr or expected_rr < 0:
                raise ValueError('事件序号/位置/RR不一致')
            self.event_next += 1; self.event_pos = frame.pos
        elif isinstance(frame, Telemetry):
            if frame.event_drop != 0 or frame.tx_drop != 0 or frame.flags != 'NA' or frame.source_drop is not None:
                raise ValueError('结果报告丢弃，不能作为完整成功')
        elif isinstance(frame, Log):
            if frame.level == 'E':
                raise OSError(frame.text)
            if frame.text.startswith('END reason=completed '):
                if self.waiting != 'F':
                    raise ValueError('非结束阶段收到END')
                if frame.text != f'END reason=completed samples={self.confirmed} events={self.event_next-1}':
                    raise ValueError('END统计与接收结果不一致')
                self.end_seen = True
        else:
            raise ValueError('输入控制与结果协议混用')
        self.monitor.feed(line)
        if self.monitor.decoder.counts['invalid'] or self.monitor.counts['wave_gap'] or self.monitor.counts['event_gap']:
            raise ValueError('结果解析/序号异常')

    def pump(self):
        if self.done:
            return
        data = self.port.read(4096)
        if data:
            self.log('usb_rx.log', data)
            for byte in data:
                self.lines.append(byte)
                if len(self.lines) > 256:
                    raise ValueError('USB结果/确认行超长')
                if byte == 10:
                    line = bytes(self.lines); self.lines.clear()
                    self._line(line)
        now = self.clock()
        if not self.boot_seen and now>=self.boot_deadline:
            raise TimeoutError('等待板端初始化就绪超时；检查应用和重新Run')
        if not self.started and self.boot_seen:
            self.started = True
            self._send(encode(f'I,ECG-IN-1,{self.session},{self.rate},{self.source},{self.scale if self.scale is not None else -1}'), 'I')
        if self.started and self.waiting is None and not self.done:
            if self.queue and (len(self.queue) >= 32 or self.eof or now - self.last_batch >= .064):
                self.inflight = tuple(self.queue.popleft() for _ in range(min(32, len(self.queue))))
                self._send(samples(self.confirmed, self.inflight), 'D'); self.last_batch = now
            elif self.eof and not self.queue:
                self._send(encode(f'F,{self.confirmed}'), 'F')
        if self.pending:
            count = self.port.write(self.pending)
            if not isinstance(count, int) or not 0 <= count <= len(self.pending):
                raise OSError('串口部分写长度错误')
            if count:
                self.log('upload.log', self.pending[:count]); self.pending = self.pending[count:]
        if self.waiting and now >= self.deadline:
            raise TimeoutError('等待确认/发送超时；停止保留现场，不自动重传')

    def summary(self):
        return dict(source_samples=self.received, confirmed=self.confirmed, echoed=self.echoed,
                    queue_peak=self.peak, done=self.done, pending_bytes=len(self.pending),
                    incomplete_rx_bytes=len(self.lines), upstream_source_drop=None,
                    sample_age_s=None if self.last_wave_at is None else max(0.,self.clock()-self.last_wave_at),
                    timing=self.metrics.summary(), timing_scope='PC roundtrip includes write, transport, board work and read; not board compute')
