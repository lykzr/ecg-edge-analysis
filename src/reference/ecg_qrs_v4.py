"""在已冻结流式GQRS上增加近邻宽波确认；独立版本，保留v3失败证据。"""
from dataclasses import asdict, dataclass
from gqrs_stream import StreamConfig, StreamDetector


@dataclass(frozen=True)
class ShapeConfig(StreamConfig):
    threshold: float = 1.5
    inspect_ms: int = 400
    slope_fraction: float = .5
    biphasic_fraction: float = .25
    amplitude_rescue_fraction: float = .75

    def __post_init__(self):
        super().__post_init__()
        if not self.refractory_ms<=self.inspect_ms<=600:
            raise ValueError('近邻检查范围无效')
        if not all(0<x<1 for x in (self.slope_fraction,self.biphasic_fraction,self.amplitude_rescue_fraction)):
            raise ValueError('形态比例无效')


class ShapeDetector(StreamDetector):
    def __init__(self, config=ShapeConfig()):
        super().__init__(config)

    def reset(self):
        super().reset()
        self.last_shape = None
        self.nearby_rejections = 0
        return []

    def putann(self, annotation):
        previous = self.last_position
        count = len(self.pending_events)
        super().putann(annotation)
        if len(self.pending_events)==count:
            return
        _,position,_ = self.pending_events[-1]
        cfg = self.config
        width = cfg.sampling_hz*80//1000
        radius = cfg.sampling_hz*150//1000
        lo,hi = max(0,position-radius),min(self.received,position+radius)
        # 基线只取中心外侧，避免宽负波本身把中位数拉低而假装成双相波。
        baseline_values = sorted([self.raw_at(i) for i in range(lo,max(lo,position-width))]
                                 +[self.raw_at(i) for i in range(min(hi+1,position+width+1),hi+1)])
        if not baseline_values:
            baseline_values = sorted(self.raw_at(i) for i in range(lo,hi+1))
        baseline = baseline_values[len(baseline_values)//2]
        lo,hi = max(0,position-width),min(self.received,position+width)
        raw = [self.raw_at(i) for i in range(lo,hi+1)]
        positive,negative = max(raw)-baseline,baseline-min(raw)
        amplitude = max(positive,negative,1.)
        biphasic = max(0.,min(positive,negative))/amplitude
        slope = max(self.variation[i%cfg.input_capacity] for i in range(lo,hi+1))
        if (previous is not None and self.last_shape is not None
            and position-previous<cfg.sampling_hz*cfg.inspect_ms//1000
            and slope/amplitude<cfg.slope_fraction*self.last_shape[0]/max(1.,self.last_shape[1])
            and biphasic<cfg.biphasic_fraction
            and amplitude<cfg.amplitude_rescue_fraction*self.last_shape[1]):
            self.pending_events.pop()
            self.last_position = previous
            self.nearby_rejections += 1
            return
        self.last_shape = slope,amplitude


def replay(samples, configuration=None):
    cfg = ShapeConfig(**(configuration or {}))
    model = ShapeDetector(cfg)
    events = []
    for sample in samples:
        events.extend(model.push(sample))
    details = dict(config=asdict(cfg),causality='BOUNDED_STREAM_NO_FUTURE_READ_NO_EOF_PADDING',
        initialization='fixed physical thresholds; no complete-record learning',
        input_buffer_samples=len(model.raw),filter_buffer_samples=len(model.qfv),peak_slots=model.c._NPEAKS,
        stale_events=model.stale_events,duplicate_events=model.duplicate_events,
        quality_rejections=model.quality_rejections,nearby_rejections=model.nearby_rejections,
        max_event_age_samples=model.max_event_age)
    return [i for _,i,_ in events],events,details
