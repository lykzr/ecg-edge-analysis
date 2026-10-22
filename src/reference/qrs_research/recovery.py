"""只在长RR回查原核心弱峰，T波由原波形判断；保留固定物理门槛。"""
from ecg_qrs_v5 import Detector as Original
from ecg_qrs_v4 import ShapeConfig
from dataclasses import asdict
from .recovery_core import steps
class Detector(Original):
    def reset(self):
        super().reset();self.generator=steps(self);next(self.generator)
        return []
def replay(samples,configuration=None):
    m=Detector(ShapeConfig(**(configuration or {})));events=[]
    for x in samples:events.extend(m.push(x))
    return [i for _,i,_ in events],events,dict(config=asdict(m.config),quality_rejections=m.quality_rejections,
        nearby_rejections=m.nearby_rejections,causality='BOUNDED_NO_FUTURE_READ_NO_EOF_PADDING')
