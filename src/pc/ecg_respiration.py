"""CH1呼吸显示滤波：500Hz因果处理，保留原码，不输出呼吸率或物理单位。"""
import math


class RespirationFilter:
    """0.05Hz一阶高通 + 0.8Hz二阶Butterworth低通；状态跨传输块保留。"""
    def __init__(self, sampling_hz=500):
        self.hp = 1 / (1 + 2 * math.pi * 0.05 / sampling_hz)
        k = math.tan(math.pi * 0.8 / sampling_hz)
        norm = 1 / (1 + math.sqrt(2) * k + k * k)
        self.b0 = k * k * norm
        self.a1 = 2 * (k * k - 1) * norm
        self.a2 = (1 - math.sqrt(2) * k + k * k) * norm
        self.previous_index = None
        self.previous_input = self.high = self.z1 = self.z2 = 0.

    @staticmethod
    def metadata():
        return dict(id='ch1-resp-display-v1', sampling_hz=500,
                    highpass_hz=0.05, lowpass_hz=0.8, lowpass_order=2,
                    lowpass_type='Butterworth_bilinear', causal=True,
                    unit='ADC code, uncalibrated', location='PC',
                    initialization='first_input_y0=0', reset='new_session_or_index_gap',
                    startup_settling_seconds=10, purpose='waveform_display_only')

    def process(self, index, code):
        if not math.isfinite(code):
            raise ValueError('呼吸原码必须为有限数值')
        if self.previous_index is None or index != self.previous_index + 1:
            self.previous_input = code
            self.high = self.z1 = self.z2 = 0.
        self.high = self.hp * (self.high + code - self.previous_input)
        low = self.b0 * self.high + self.z1
        self.z1 = 2 * self.b0 * self.high - self.a1 * low + self.z2
        self.z2 = self.b0 * self.high - self.a2 * low
        self.previous_input, self.previous_index = code, index
        return low
