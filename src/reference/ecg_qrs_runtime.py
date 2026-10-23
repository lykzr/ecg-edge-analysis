"""研究26的有界逐样本软件运行时；360Hz等价候选，500Hz转换另验。

冻结算法不修改；不保留全输入、全事件或逐拍audit，不代表整数/PS/PL实现。
"""
from collections import deque
from dataclasses import dataclass
from statistics import median
import math

from ecg_qrs_v4 import ShapeConfig
from qrs_research.candidate import Detector as Primary
from qrs_research.gradient import Detector as Secondary


def round_ratio(numerator, denominator):
    """有符号对称四舍五入；不使用Python的银行家舍入。"""
    if denominator <= 0:
        raise ValueError('分母必须为正')
    value = (abs(numerator) + denominator // 2) // denominator
    return -value if numerator < 0 else value


@dataclass(frozen=True)
class AdcScale:
    """显式ADC零点和ADC/mV增益；不得从数据形态反推标定。"""
    baseline: int
    counts_per_mv: int
    units_per_mv: int = 4096

    def __post_init__(self):
        if any(type(v) is not int for v in (self.baseline, self.counts_per_mv, self.units_per_mv)):
            raise ValueError('幅值合同必须使用整数')
        if self.counts_per_mv <= 0 or self.units_per_mv != 4096:
            raise ValueError('需要明确的ADC/mV增益，当前算法固定4096单位/mV')

    def convert(self, value):
        if type(value) is not int:
            raise ValueError('ADC码值必须为整数')
        mapped = round_ratio((value - self.baseline) * self.units_per_mv, self.counts_per_mv)
        return min(32767, max(-32768, mapped)), not -32768 <= mapped <= 32767


class ResearchRuntime:
    """每次push一个360Hz int16样本，输出(emitted, position, rr)。"""
    capacity = 4096
    queue_capacity = 32

    def __init__(self, configuration=None):
        self.configuration = dict(configuration or {})
        self.configuration.setdefault('threshold', 1.0)
        self.reset()

    def reset(self):
        self.primary = Primary(ShapeConfig(**self.configuration))
        # 冻结candidate仅追加audit，从不读取；禁留历史不改变判决或模板学习。
        self.primary.audit = deque(maxlen=0)
        self.secondary = Secondary(360)
        self.raw = [0] * self.capacity
        self.pending = deque()
        self.cache = deque(maxlen=self.queue_capacity)
        self.index = -1
        self.last_position = None
        self.changed = self.tail_pending = self.max_pending = 0
        self.closed = False
        return []

    def at(self, index):
        if not max(0, self.index - self.capacity + 1) <= index <= self.index:
            raise IndexError('禁止读取未来或已覆盖的样本')
        return self.raw[index % self.capacity]

    def push(self, sample=0, valid=True, reset_n=True, sequence=None):
        if not reset_n:
            return self.reset()
        if self.closed:
            raise RuntimeError('会话已结束，须显式reset')
        if type(sample) is not int or not -32768 <= sample <= 32767:
            raise ValueError('需要360Hz、4096单位/mV的int16输入')
        if not valid:
            return []
        if sequence is not None and (type(sequence) is not int or sequence != self.index + 1):
            raise ValueError('样本号缺口/重复；须显式结束并重置会话')
        self.index += 1
        self.raw[self.index % self.capacity] = sample
        self.cache.extend(self.secondary.push(sample))
        for emitted, position, _ in self.primary.push(sample):
            if len(self.pending) >= self.queue_capacity:
                raise OverflowError('待确认队列满，停止会话，不静默丢事件')
            self.pending.append((emitted + 72, position))
        self.max_pending = max(self.max_pending, len(self.pending))
        output = []
        while self.pending and self.pending[0][0] <= self.index:
            deadline, position = self.pending.popleft()
            while self.cache and deadline - self.cache[0][0] > 1440:
                self.cache.popleft()
            nearby = [e for e in self.cache if 0 < abs(e[1] - position) <= 10]
            if nearby:
                alternate = min(nearby, key=lambda e: abs(e[1] - position))[1]
                lo, hi = sorted((position, alternate))
                flank = [self.at(i) for i in range(max(0, lo - 54), max(0, lo - 28))]
                flank += [self.at(i) for i in range(hi + 29, min(deadline, hi + 54) + 1)]
                baseline = median(flank) if flank else self.at(position)
                a, b = self.at(position) - baseline, self.at(alternate) - baseline
                if a * b < 0 and .8 <= abs(b / a) <= 1.25 and (
                    self.last_position is None or alternate > self.last_position
                ):
                    position = alternate
                    self.changed += 1
            rr = 0 if self.last_position is None else position - self.last_position
            self.last_position = position
            output.append((deadline, position, rr))
        return output

    def finish(self):
        """记录尚未到截止的候选，不补零、不提前输出、不制造尾部事件。"""
        if not self.closed:
            self.tail_pending = len(self.pending)
            self.pending.clear()
            self.closed = True
        return dict(tail_pending=self.tail_pending, changed=self.changed,
                    max_pending=self.max_pending, runtime_implementation=True,
                    qualified=False, sampling_hz=360, memory_scope='fixed sample/event/template buffers; Python float reference only')


class RateAdapter:
    """500→360Hz：61抽头90Hz低通、线性有理重采样；360Hz原样通过。

    500Hz为独立候选。位置只扣除FIR固定30点群延迟，不拟合标注偏移。
    物理事件位置回到源采样号；emitted仍是实际等待到的源采样号。
    """
    def __init__(self, sampling_hz=360):
        if sampling_hz not in (360, 500):
            raise ValueError('仅支持360/500Hz')
        self.rate = sampling_hz
        self.delay = 30 if sampling_hz == 500 else 0
        if self.delay:
            from scipy.signal import firwin
            self.coefficients = tuple(float(x) for x in firwin(61, 90, fs=500))
        else:
            self.coefficients = (1.,)
        self.reset()

    def reset(self):
        self.index = -1
        self.next_output = 0
        self.previous = 0.
        self.history = deque(maxlen=len(self.coefficients))

    def push(self, sample):
        self.index += 1
        if self.rate == 360:
            return [(self.index, sample)]
        if not self.history:
            self.history.extend([float(sample)] * len(self.coefficients))
        self.history.appendleft(float(sample))
        current = sum(c * x for c, x in zip(self.coefficients, self.history))
        output = []
        while self.next_output * self.rate <= self.index * 360:
            t = self.next_output * self.rate
            fraction = (t - (self.index - 1) * 360) / 360
            value = self.previous + fraction * (current - self.previous) if self.index else current
            rounded = int(math.copysign(math.floor(abs(value) + .5), value))
            output.append((self.next_output, min(32767, max(-32768, rounded))))
            self.next_output += 1
        self.previous = current
        return output

    def source_index(self, position):
        return round_ratio(position * self.rate, 360) - self.delay


class InputRuntime:
    """源样本编号从0开始；可选显式ADC换算；不接受蓝牙厂商帧或串口协议。"""
    def __init__(self, sampling_hz=360, scale=None, configuration=None):
        self.rate = sampling_hz
        self.scale = scale
        self.detector = ResearchRuntime(configuration)
        self.adapter = RateAdapter(sampling_hz)
        self.reset()

    def reset(self):
        self.detector.reset()
        self.adapter.reset()
        self.index = -1
        self.last_position = None
        self.clipped = self.startup_events = 0
        self.closed = False

    def push(self, sample, sequence=None, valid=True):
        if self.closed:
            raise RuntimeError('会话已结束')
        if not valid:
            return []
        if sequence is not None and (type(sequence) is not int or sequence != self.index + 1):
            raise ValueError('源样本号不连续；禁止将缺口拼成连续RR')
        if self.scale is not None:
            sample, clipped = self.scale.convert(sample)
            self.clipped += clipped
        elif type(sample) is not int or not -32768 <= sample <= 32767:
            raise ValueError('没有幅值合同时只接收int16')
        self.index += 1
        events = []
        for internal, value in self.adapter.push(sample):
            for _, position, _ in self.detector.push(value, sequence=internal):
                source = self.adapter.source_index(position)
                if source < 0:
                    self.startup_events += 1
                    continue
                if self.last_position is not None and source <= self.last_position:
                    raise ArithmeticError('映射后事件位置不递增')
                rr = 0 if self.last_position is None else source - self.last_position
                events.append((self.index, source, rr))
                self.last_position = source
        return events

    def finish(self):
        self.closed = True
        return dict(self.detector.finish(), source_sampling_hz=self.rate,
                    source_samples=self.index + 1, clipped=self.clipped,
                    startup_events=self.startup_events, fir_delay_source_samples=self.adapter.delay)
