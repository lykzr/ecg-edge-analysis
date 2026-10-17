"""逐样本因果双二阶滤波参考：浮点状态，末级对称舍入/饱和至int16；未实现RTL。"""
import cmath
import math


def coefficients(kind, frequency, sampling_hz=360, q=math.sqrt(0.5)):
    """归一化RBJ双二阶系数；公式来源W3C Audio EQ Cookbook。"""
    if not 0 < frequency < sampling_hz / 2 or not q > 0:
        raise ValueError('频率必须低于奈奎斯特频率且Q为正')
    w = 2 * math.pi * frequency / sampling_hz
    c, alpha = math.cos(w), math.sin(w) / (2*q)
    if kind == 'highpass':
        b = ((1+c)/2, -(1+c), (1+c)/2)
    elif kind == 'lowpass':
        b = ((1-c)/2, 1-c, (1-c)/2)
    elif kind == 'notch':
        b = (1, -2*c, 1)
    else:
        raise ValueError('未知滤波器类型')
    return tuple(x/(1+alpha) for x in (*b, -2*c, 1-alpha))


class Biquad:
    def __init__(self, values):
        self.values = values
        self.reset()

    def reset(self):
        self.z1 = self.z2 = 0.0

    def tick(self, x):
        b0, b1, b2, a1, a2 = self.values
        y = b0*x + self.z1
        self.z1 = b1*x - a1*y + self.z2
        self.z2 = b2*x - a2*y
        return y

    def response(self, frequency, sampling_hz=360):
        z = cmath.exp(-2j*math.pi*frequency/sampling_hz)
        b0,b1,b2,a1,a2 = self.values
        return (b0+b1*z+b2*z*z)/(1+a1*z+a2*z*z)


class Filter:
    def __init__(self, profile, sampling_hz=360, highpass_hz=.5,
                 lowpass_hz=40, notch_hz=60, notch_q=30):
        if profile not in ('raw', 'bandpass', 'notch', 'bandpass_notch'):
            raise ValueError('未知滤波配置')
        self.stages = []
        if profile in ('bandpass', 'bandpass_notch'):
            self.stages += [Biquad(coefficients('highpass',highpass_hz,sampling_hz)),
                            Biquad(coefficients('lowpass',lowpass_hz,sampling_hz))]
        if profile in ('notch', 'bandpass_notch'):
            self.stages.append(Biquad(coefficients('notch',notch_hz,sampling_hz,notch_q)))
        self.reset()

    def reset(self):
        for stage in self.stages:
            stage.reset()
        self.clipped = 0

    def tick(self, x):
        for stage in self.stages:
            x = stage.tick(x)
        if not math.isfinite(x):
            raise ArithmeticError('滤波状态出现非有限数')
        y = int(math.copysign(math.floor(abs(x)+.5),x))
        self.clipped += int(not -32768 <= y <= 32767)
        return min(32767,max(-32768,y))
