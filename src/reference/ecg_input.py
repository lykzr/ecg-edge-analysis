"""离线输入幅值约定与无标注启动校准；尚未接入 PS/RTL。"""
from collections import deque
from dataclasses import replace


def map_adc(values, baseline, gain, units_per_mv=4096):
    """按头文件 ADC/mV 转为固定整数/mV；对称四舍五入并饱和至16位。"""
    if gain <= 0 or units_per_mv <= 0:
        raise ValueError('增益与目标单位必须为正整数')
    result, clipped = [], 0
    for value in values:
        numerator = (value-baseline)*units_per_mv
        magnitude = (abs(numerator) + gain//2)//gain
        sample = -magnitude if numerator < 0 else magnitude
        clipped += int(not -32768 <= sample <= 32767)
        result.append(max(-32768, min(32767, sample)))
    return result, clipped


def calibrate(samples, config, seconds=2):
    """只读启动段：完整窗口能量的中位数/90分位数作噪声/信号初值。"""
    count = config.sample_rate_hz*seconds
    if seconds <= 0 or count > len(samples) or count <= config.window_length:
        raise ValueError('校准段不足一个完整窗口，或超出记录')
    window, total, energies = deque(), 0, []
    for previous, current in zip(samples[:count-1], samples[1:count]):
        difference = abs(current-previous)
        window.append(difference); total += difference
        if len(window) > config.window_length:
            total -= window.popleft()
        if len(window) == config.window_length:
            energies.append(total)
    ordered = sorted(energies)
    noise = max(1, ordered[(len(ordered)-1)*50//100])
    signal = max(noise+1, ordered[(len(ordered)-1)*90//100])
    if signal >= (1 << config.energy_width):
        raise ValueError('校准能量超出检测器位宽')
    return replace(config, initial_noise_level=noise, initial_signal_level=signal), dict(
        samples=count, seconds=seconds, complete_windows=len(energies),
        method='sorted full-window abs differences at floor((n-1)*p), p=0.5/0.9; no annotations',
        initial_noise_level=noise, initial_signal_level=signal,
        initial_threshold=noise+((signal-noise)>>2),
        startup_policy='buffer prefix, estimate, reset detector and replay whole record; two-second startup buffering')
