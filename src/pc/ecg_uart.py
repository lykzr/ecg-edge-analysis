"""ECG-UART-1软件v1的有界流解析；不依赖采集设备或第三方模块。"""
from collections import Counter
from dataclasses import dataclass
import math
import re

VERSION = 'ECG-UART-1'
MASK = 0xFFFFFFFF
RAW, FILT, EVENT, STATUS, CLASS, COMMAND = (1 << i for i in range(6))
MAX_LINE = 256


class ProtocolError(ValueError):
    pass


def integer(value, low=0, high=MASK):
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)', value):
        raise ProtocolError('整数格式错误')
    result = int(value)
    if not low <= result <= high:
        raise ProtocolError('整数越界')
    return result


def number(value):
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', value):
        raise ProtocolError('小数格式错误')
    result = float(value)
    if not math.isfinite(result) or (result < 0 and result != -1):
        raise ProtocolError('小数越界')
    return None if result == -1 else result


def optional_int(value):
    return None if value == '-1' else integer(value)


def token(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', value):
        raise ProtocolError('元数据标识格式错误')
    return value


@dataclass(frozen=True)
class Header:
    firmware: str
    session: str
    source: str
    detector: str
    fs: int | None
    scale: int | None
    caps: int


@dataclass(frozen=True)
class Wave:
    seq0: int
    pairs: tuple


@dataclass(frozen=True)
class Event:
    seq: int
    pos: int
    rr: int
    hr: float | None
    cls: str
    conf: int | None


@dataclass(frozen=True)
class Telemetry:
    hr: float | None
    rr_ms: float | None
    cls: str
    flags: str
    fs: int | None
    event_drop: int | None
    source_drop: int | None
    tx_drop: int | None
    uptime_ms: int


@dataclass(frozen=True)
class Log:
    level: str
    text: str


@dataclass(frozen=True)
class Ack:
    command_id: int
    status: str


def classified(value, header):
    if value not in ('N', 'S', 'V', 'F', '?') or (value != '?' and not header.caps & CLASS):
        raise ProtocolError('分类值或能力不符')
    return value


def parse_line(line, header=None):
    """完整非空ASCII行；失败前不改变任何会话/计数状态。"""
    fields = line.split(',')
    label = fields[0]
    if label == 'H':
        if len(fields) != 9 or fields[1] != VERSION:
            raise ProtocolError('H需要当前软件v1的9个字段；旧草案不是兼容接口')
        _, _, firmware, session, source, detector, fs, scale, caps = fields
        if source not in ('SYNTH', 'REPLAY', 'ADC', 'UNKNOWN'):
            raise ProtocolError('未知来源枚举')
        if not re.fullmatch(r'0x[0-9A-Fa-f]{1,8}', caps):
            raise ProtocolError('能力位需要0x前缀')
        caps = int(caps, 16)
        if caps & (1 << 6):
            raise ProtocolError('此版本不支持行校验；不能猜测校验算法')
        fs = optional_int(fs); scale = optional_int(scale)
        if fs == 0 or scale == 0:
            raise ProtocolError('fs/scale必须为正或-1')
        return Header(token(firmware), token(session), source, token(detector), fs, scale, caps)
    if header is None:
        raise ProtocolError('数据前缺少H元数据')
    if label == 'W':
        if not header.caps & RAW or len(fields) < 5:
            raise ProtocolError('W缺少能力或字段')
        seq = integer(fields[1]); n = integer(fields[2], 1, 8)
        if len(fields) != 3 + 2 * n:
            raise ProtocolError('W数量与样本对不符')
        pairs = []
        for i in range(n):
            raw = integer(fields[3 + 2*i], -32768, 32767)
            filt = None if fields[4 + 2*i] == 'NA' else integer(fields[4 + 2*i], -32768, 32767)
            if filt is not None and not header.caps & FILT:
                raise ProtocolError('未声明滤波能力却给出了滤波值')
            pairs.append((raw, filt))
        return Wave(seq, tuple(pairs))
    if label == 'E':
        if not header.caps & EVENT or len(fields) != 7:
            raise ProtocolError('E缺少能力或字段')
        seq, pos, rr = (integer(x) for x in fields[1:4]); hr = number(fields[4])
        cls = classified(fields[5], header)
        conf = None if fields[6] == '-1' else integer(fields[6], 0, 100)
        if cls == '?' and conf is not None:
            raise ProtocolError('未知分类不能给虚构置信分数')
        if not rr or header.fs is None:
            if hr is not None:
                raise ProtocolError('RR/fs未知时心率必须未知')
        elif hr is not None and abs(hr - 60 * header.fs / rr) > .051:
            raise ProtocolError('瞬时心率与RR/fs不一致')
        return Event(seq, pos, rr, hr, cls, conf)
    if label == 'T':
        if not header.caps & STATUS or len(fields) != 10:
            raise ProtocolError('T缺少能力或字段')
        hr, rr = number(fields[1]), number(fields[2]); cls = classified(fields[3], header)
        flags = fields[4]; words = flags.split('|')
        if (len(set(words)) != len(words) or
                not set(words) <= {'OK', 'NA', 'OVF', 'CLIP', 'SOURCE_DROP', 'TX_DROP'} or
                (len(words) > 1 and ('OK' in words or 'NA' in words))):
            raise ProtocolError('状态标志错误')
        fs = optional_int(fields[5])
        if fs != header.fs or (fs is None and (hr is not None or rr is not None)):
            raise ProtocolError('状态采样率与会话不一致')
        if hr == 0 or rr == 0:
            raise ProtocolError('未知心率/RR用-1，不用0')
        return Telemetry(hr, rr, cls, flags, fs, *(optional_int(x) for x in fields[6:9]), integer(fields[9]))
    if label == 'L':
        fields = line.split(',', 2)
        if len(fields) != 3 or fields[1] not in ('I', 'W', 'E'):
            raise ProtocolError('日志格式错误')
        return Log(fields[1], fields[2])
    if label == 'K':
        if not header.caps & COMMAND or len(fields) != 3 or fields[2] not in ('OK', 'ERR', 'BUSY', 'UNKNOWN'):
            raise ProtocolError('命令应答错误')
        return Ack(integer(fields[1]), fields[2])
    raise ProtocolError('未知类型')


class Decoder:
    """按字节接收，超长行只计错一次并恢复；回调只得到完整合法报文。"""
    def __init__(self, callback=None):
        self.callback = callback
        self.buffer = bytearray()
        self.discarding = False
        self.header = None
        self.sessions = set()
        self.counts = Counter()
        self.last_error = ''

    def feed(self, data):
        for byte in data:
            self.counts['bytes'] += 1
            if self.discarding:
                if byte == 10:
                    self.discarding = False
                continue
            if byte == 10:
                try:
                    if len(self.buffer) + 1 > MAX_LINE:
                        self._bad('超长行', 'overlong')
                    else:
                        self._line(bytes(self.buffer))
                finally:
                    self.buffer.clear()
            elif len(self.buffer) >= MAX_LINE - 1:
                self._bad('超长行', 'overlong')
                self.buffer.clear(); self.discarding = True
            else:
                self.buffer.append(byte)

    def _bad(self, message, kind='invalid'):
        self.counts[kind] += 1
        self.last_error = message[:256]

    def _line(self, data):
        if data.endswith(b'\r'):
            data = data[:-1]
        if not data:
            self.counts['empty'] += 1
            return
        if any(b < 32 or b > 126 for b in data):
            self._bad('非ASCII或控制字符')
            return
        line = data.decode('ascii'); label = line.split(',', 1)[0]
        if label not in {'H', 'W', 'E', 'T', 'L', 'K'}:
            self.counts['unknown'] += 1
            self.last_error = line[:256]
            return
        try:
            frame = parse_line(line, self.header)
            if isinstance(frame, Header):
                if self.header is not None and frame.session == self.header.session:
                    if frame != self.header:
                        raise ProtocolError('同一session的元数据不能改变')
                    self.counts['duplicate_header'] += 1
                    return
                if frame.session in self.sessions:
                    raise ProtocolError('旧session不能在新会话后再次复用')
                if len(self.sessions) >= 256:
                    raise ProtocolError('单个文件会话过多；请拆分日志')
            if self.callback:
                self.callback(frame)
            if isinstance(frame, Header):
                self.header = frame; self.sessions.add(frame.session)
                if frame.caps & ~0x3F:
                    self.counts['unknown_caps'] += 1
            self.counts[label] += 1
        except ProtocolError as error:
            self._bad(str(error))

    def finish(self):
        if self.buffer:
            self._bad('文件末尾是不完整行', 'truncated')
        self.buffer.clear(); self.discarding = False
