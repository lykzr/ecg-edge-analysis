"""PC心电显示处理；不改变板端或模型输入，不按人体典型幅值缩放。"""
import math
from ecg_bridge_capture import NominalConverter
from ecg_filter_reference import Biquad, coefficients


class EcgDisplayFilter:
    def __init__(self):
        self.alpha = 500 / (500 + 2 * math.pi * .5)
        self.previous_index = None
        self.previous_code = self.high = 0.
        self.stages = [Biquad(coefficients('lowpass', 40, 500)),
                       Biquad(coefficients('notch', 50, 500, 30))]

    @staticmethod
    def metadata():
        return dict(id='ch2-ecg-display-v1', location='PC', sampling_hz=500,
                    baseline_highpass_hz=.5, baseline_method='backward_euler_first_order',
                    display_lowpass_hz=40, display_lowpass_order=2,
                    display_notch_hz=50, display_notch_q=30, causal=True,
                    initialization='first_input_y0=0', reset='new_session_or_index_gap',
                    startup_settling_seconds=5, calibrated=False,
                    adc_denominator=8388607, vref_mv=2420, pga_gain=6,
                    amplitude_normalization=False, purpose='rhythm_display_only_not_ST_analysis')

    def process(self, index, code):
        if not math.isfinite(code):
            raise ValueError('心电原码必须为有限数值')
        if self.previous_index is None or index != self.previous_index + 1:
            self.previous_code, self.high = code, 0.
            for stage in self.stages:
                stage.reset()
        self.high = self.alpha * (self.high + code - self.previous_code)
        display = self.high
        for stage in self.stages:
            display = stage.tick(display)
        self.previous_index, self.previous_code = index, code
        factor = 2420 / NominalConverter.denominator
        return dict(ecg_baseline_code=self.high, ecg_baseline_mv=self.high * factor,
                    ecg_display_code=display, ecg_display_mv=display * factor)
