"""候选峰算法的软件原型；尚未移植 RTL，不是旧 RTL 的逐周期模型。"""
from collections import deque
from dataclasses import dataclass
from ecg_reference import Config


@dataclass(frozen=True)
class PeakState:
    qrs_valid: int
    qrs_sample_index: int
    rr_interval_samples: int
    integrated_energy: int
    adaptive_threshold: int


class PeakDetector:
    """固定窗口差分能量，在局部峰确认后更新信号估计并定位原波形极值。"""
    def __init__(self, config=Config()):
        if config.sample_width != 16 or 65535*config.window_length >= (1 << config.energy_width):
            raise ValueError('峰值原型只支持16位输入及足以容纳窗口和的能量位宽')
        self.config = config
        self.reset()

    def reset(self):
        c = self.config
        self.index = -1
        self.previous_sample = None
        self.differences = deque()
        self.waveform = deque(maxlen=3*c.window_length+8)
        self.integrated_energy = 0
        self.noise_level = c.initial_noise_level
        self.signal_level = c.initial_signal_level
        self.older_energy = self.previous_energy = 0
        self.pending = None
        self.last_qrs = None
        self.last_index = self.last_rr = 0
        return self.state(0)

    def threshold(self):
        return max(1, self.noise_level + max(0,self.signal_level-self.noise_level)//4)

    def state(self, valid):
        return PeakState(valid,self.last_index,self.last_rr,
                         self.integrated_energy,self.threshold())

    def tick(self, sample=0, valid=True, reset_n=True):
        if not reset_n:
            return self.reset()
        if not -32768 <= sample <= 32767:
            raise ValueError('输入必须为16位有符号整数')
        if not valid:
            return self.state(0)
        self.index += 1
        self.waveform.append((self.index,sample))
        if self.previous_sample is not None:
            difference = abs(sample-self.previous_sample)
            self.differences.append(difference)
            self.integrated_energy += difference
            if len(self.differences) > self.config.window_length:
                self.integrated_energy -= self.differences.popleft()
        self.previous_sample = sample
        energy = self.integrated_energy
        # 下降沿确认上一点的局部峰；平顶取下降前最后一个点。
        is_peak = self.previous_energy >= self.older_energy and self.previous_energy > energy
        if is_peak:
            peak_index, peak_energy = self.index-1,self.previous_energy
            if self.pending is not None:
                if peak_energy > self.pending[1]:
                    # 确认截止位置固定，不让噪声峰无限推迟输出。
                    self.pending = (peak_index,peak_energy,self.pending[2])
            elif self.last_qrs is None or peak_index-self.last_qrs >= self.config.refractory_length:
                if peak_energy >= self.threshold():
                    self.pending = (peak_index,peak_energy,
                                    self.index+max(1,self.config.window_length//2))
                else:
                    self.noise_level = (7*self.noise_level+peak_energy)//8
        emitted = 0
        if self.pending is not None and self.index >= self.pending[2]:
            peak_index,peak_energy,_ = self.pending
            # 在能量峰对应的原始积分窗口定位偏离局部中位数最大的点，支持负向QRS。
            region = [(i,x) for i,x in self.waveform
                      if peak_index-self.config.window_length+1 <= i <= peak_index]
            baseline = sorted(x for _,x in region)[len(region)//2]
            qrs_index,_ = max(region,key=lambda item:abs(item[1]-baseline))
            if self.last_qrs is None or qrs_index-self.last_qrs >= self.config.refractory_length:
                self.last_rr = 0 if self.last_qrs is None else qrs_index-self.last_qrs
                self.last_index = self.last_qrs = qrs_index
                self.signal_level = (7*self.signal_level+peak_energy)//8
                emitted = 1
            self.pending = None
        self.older_energy,self.previous_energy = self.previous_energy,energy
        return self.state(emitted)
