"""离线软件参考的输入→逐样本检测→切拍接口；不接管PC显示或板端协议。"""
from ecg_qrs_runtime import InputRuntime
from ecg_beat_window import BeatCutter


class SignalPipeline:
    """源波形和切拍共用一次幅值转换；事件保持源采样号，不推断疾病。"""
    def __init__(self, sampling_hz=360, scale=None):
        self.scale = scale
        self.detector = InputRuntime(sampling_hz)
        self.cutter = BeatCutter(sampling_hz)
        self.reset()

    def reset(self):
        self.detector.reset()
        self.cutter.reset()
        self.clipped = 0
        self.closed = False

    def push(self, value, sequence=None):
        if self.closed:
            raise RuntimeError('会话已结束，须reset后重新开始')
        if sequence is not None and (type(sequence) is not int or sequence != self.detector.index + 1):
            raise ValueError('源样本号不连续；须显式reset，不能跨缺口算RR')
        if self.scale is not None:
            value, clipped = self.scale.convert(value)
            self.clipped += clipped
        events = self.detector.push(value, sequence=sequence)
        windows = self.cutter.push(value, events, sequence=sequence)
        return events, windows

    def finish(self):
        self.closed = True
        return dict(detector=self.detector.finish(), windows=self.cutter.finish(), clipped=self.clipped,
                    cnn_inference=False, ps_pl=False, real_acquisition=False)
