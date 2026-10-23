"""自动检测位置驱动的有界原波形切拍；未分类，不使用专家标注补峰。"""
from collections import deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BeatWindow:
    position: int
    emitted: int
    rr_samples: int
    sampling_hz: int
    before: int
    samples: tuple
    rr_history: tuple
    units_per_mv: int = 4096

    def model_input(self):
        """复用训练端窗口变换，输出128点；首拍无RR，返回None而非伪造特征。"""
        from pathlib import Path
        import sys
        import json
        import numpy as np
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / 'model/prepare'))
        from prepare_cnn_expanded import common_window, causal_rr
        cfg = json.loads((root / 'model/protocols/cnn_git_v1_protocol.json').read_text(encoding='utf-8'))['window']
        waveform = common_window(np.asarray(self.samples, dtype=float) / self.units_per_mv,
                                 self.before, self.sampling_hz, cfg)
        rr = causal_rr(list(self.rr_history)) if self.rr_history else None
        return waveform, rr


class BeatCutter:
    """保持源采样号；不对短窗口补零；队列溢出/缺口明确失败。"""
    def __init__(self, sampling_hz=360, capacity=4096, pending_capacity=32):
        if sampling_hz not in (360, 500) or capacity < 2048 or pending_capacity < 1:
            raise ValueError('切拍采样率或缓冲容量无效')
        self.rate = sampling_hz
        self.before = math.ceil(sampling_hz * (128 / 360))
        self.after = math.ceil(sampling_hz * (192 / 360))
        self.capacity = capacity
        self.pending_capacity = pending_capacity
        self.reset()

    def reset(self):
        self.raw = [0] * self.capacity
        self.index = -1
        self.last_event = None
        self.pending = deque()
        self.rr_history = deque(maxlen=401)
        self.startup_skipped = self.tail_skipped = 0
        self.closed = False

    def push(self, sample, events=(), sequence=None):
        if self.closed:
            raise RuntimeError('切拍会话已结束')
        if type(sample) is not int or not -32768 <= sample <= 32767:
            raise ValueError('切拍使用4096单位/mV的int16源波形')
        if sequence is not None and (type(sequence) is not int or sequence != self.index + 1):
            raise ValueError('源样本缺口；须重置切拍历史')
        # 先校验本次事件，禁止部分失败后悄悄接着送样。
        previous = self.last_event
        for emitted, position, rr in events:
            if any(type(x) is not int for x in (emitted, position, rr)):
                raise ValueError('事件字段必须为整数')
            if emitted != self.index + 1 or not 0 <= position <= emitted:
                raise ValueError('事件必须在实际确认时送入，禁止未来位置')
            if previous is not None and (position <= previous or rr != position - previous):
                raise ValueError('事件位置/RR不连续')
            if previous is None and rr != 0:
                raise ValueError('首事件RR应为0（未知）')
            previous = position
        if len(self.pending) + len(events) > self.pending_capacity:
            raise OverflowError('待切拍队列满')
        self.index += 1
        self.raw[self.index % self.capacity] = sample
        for emitted, position, rr in events:
            if rr:
                self.rr_history.append(rr)
            self.last_event = position
            if position < self.before:
                self.startup_skipped += 1
                continue
            self.pending.append((position, rr, tuple(self.rr_history)))
        output = []
        while self.pending and self.pending[0][0] + self.after - 1 <= self.index:
            position, rr, history = self.pending.popleft()
            start, end = position - self.before, position + self.after
            if start <= self.index - self.capacity:
                raise IndexError('事件到达过晚，原波形已覆盖')
            values = tuple(self.raw[i % self.capacity] for i in range(start, end))
            output.append(BeatWindow(position, self.index, rr, self.rate, self.before, values, history))
        return output

    def finish(self):
        if not self.closed:
            self.tail_skipped = len(self.pending)
            self.pending.clear()
            self.closed = True
        return dict(startup_skipped=self.startup_skipped, tail_skipped=self.tail_skipped,
                    classified=False, padding=False)
