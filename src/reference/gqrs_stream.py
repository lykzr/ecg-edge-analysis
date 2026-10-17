"""复用MIT许可GQRS决策的有界逐样本原型；原波形定位，禁止读取尚未输入的样本。"""
from dataclasses import asdict, dataclass
import hashlib
import inspect
import json
from pathlib import Path
import sys
import numpy as np
import wfdb
from wfdb.processing.qrs import GQRS
from ecg_filter_reference import Biquad, coefficients

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/third_party'))
from gqrs_core import steps


@dataclass(frozen=True)
class StreamConfig:
    sampling_hz: int = 360
    units_per_mv: int = 4096
    core_units_per_mv: int = 4096
    refractory_ms: int = 240
    probe_ms: int = 50
    localization_radius_ms: int = 100
    localization_amplitude_fraction: float = .8
    baseline_radius_ms: int = 150
    input_capacity: int = 4096
    filter_capacity: int = 1024
    threshold: float = 1.0
    minimum_central_ratio: float = 1.0
    central_ms: int = 80
    context_ms: int = 240

    def __post_init__(self):
        if self.sampling_hz!=360 or self.units_per_mv!=4096:
            raise ValueError('当前仅核验360Hz、4096单位/mV')
        if not 64<=self.core_units_per_mv<=4096 or not .5<=self.localization_amplitude_fraction<=1:
            raise ValueError('内部幅值单位或定位比例无效')
        if self.refractory_ms<200 or not 1<=self.probe_ms<=100:
            raise ValueError('不应期或峰队列检查周期无效')
        if not 1<=self.localization_radius_ms<=self.baseline_radius_ms<=250:
            raise ValueError('定位/基线窗口无效')
        if self.input_capacity<3600 or self.filter_capacity<256 or self.filter_capacity&(self.filter_capacity-1):
            raise ValueError('原波形容量不足或滤波容量不是合适的2次幂')
        if not .1<=self.threshold<=10:
            raise ValueError('物理阈值比例无效')
        if not 0<=self.minimum_central_ratio<=4 or not 10<=self.central_ms<self.context_ms<=300:
            raise ValueError('中心/背景斜率参数无效')


class StreamDetector(GQRS):
    def __init__(self, config=StreamConfig()):
        self.config = config
        provenance = json.loads((ROOT/'src/third_party/gqrs_provenance.json').read_text(encoding='utf-8'))
        if wfdb.__version__!='4.3.1' or hashlib.sha256(Path(inspect.getfile(GQRS)).read_bytes()).hexdigest()!=provenance['upstream_module_sha256']:
            raise ValueError('WFDB实现与已审查版本不匹配')
        self.reset()

    def reset(self):
        cfg = self.config
        self.c = GQRS.Conf(fs=cfg.sampling_hz,adc_gain=cfg.core_units_per_mv,
                           RRmin=cfg.refractory_ms/1000,thresh=cfg.threshold)
        self.c._BUFLN = cfg.filter_capacity
        self.adc_zero = 0
        self.qfv = np.zeros(cfg.filter_capacity,dtype='int64')
        self.smv = np.zeros(cfg.filter_capacity,dtype='int64')
        self.v1 = 0
        self.t = -self.c.dt4
        self.annot = GQRS.Annotation(0,'NOTE',0,0)
        first = GQRS.Peak(0,0,0)
        previous = first
        for _ in range(1,self.c._NPEAKS):
            peak = GQRS.Peak(0,0,0)
            previous.next_peak = peak
            peak.prev_peak = previous
            previous = peak
        previous.next_peak = first
        first.prev_peak = previous
        self.current_peak = first
        self.state = 'RUNNING'
        self.sample_valid = True
        self.probe_samples = max(1,cfg.sampling_hz*cfg.probe_ms//1000)
        self.received = -1
        self.raw = [0]*cfg.input_capacity
        self.variation = [0.]*cfg.input_capacity
        self.quality_lowpass = Biquad(coefficients('lowpass',40,cfg.sampling_hz))
        self.previous_lowpass = None
        self.first_sample = 0
        self.pending_events = []
        self.last_position = None
        self.stale_events = self.duplicate_events = self.quality_rejections = 0
        self.max_event_age = self.max_requested_index = -1
        self.generator = steps(self)
        next(self.generator)
        return []

    def raw_at(self, index):
        if index<0:
            return self.first_sample
        if index>self.received:
            raise AssertionError('禁止读取未来输入')
        if index<=self.received-self.config.input_capacity:
            raise IndexError('读取超过原波形环形缓冲范围')
        self.max_requested_index = max(self.max_requested_index,index)
        return self.raw[index%self.config.input_capacity]

    def at(self, index):
        value = self.raw_at(index)
        numerator = value*self.config.core_units_per_mv
        magnitude = (abs(numerator)+self.config.units_per_mv//2)//self.config.units_per_mv
        return -magnitude if numerator<0 else magnitude

    def putann(self, annotation):
        center = int(annotation.time)+self.c.dt2
        radius = self.config.sampling_hz*self.config.localization_radius_ms//1000
        baseline_radius = self.config.sampling_hz*self.config.baseline_radius_ms//1000
        oldest = max(0,self.received-self.config.input_capacity+1)
        if center-baseline_radius<oldest and oldest>0:
            self.stale_events += 1
            return
        lo,hi = max(0,center-baseline_radius),min(self.received,center+baseline_radius)
        region = [self.raw_at(i) for i in range(lo,hi+1)]
        if not region:
            self.stale_events += 1
            return
        baseline = sorted(region)[len(region)//2]
        lo,hi = max(0,center-radius),min(self.received,center+radius)
        maximum = max(abs(self.raw_at(i)-baseline) for i in range(lo,hi+1))
        # 对相近幅值的双相峰，选择最接近内部滤波峰的原波形极值；不使用标注或拟合偏移。
        extrema = [i for i in range(max(1,lo),min(self.received,hi)+1)
                   if i<self.received and abs(self.raw_at(i)-baseline)>=maximum*self.config.localization_amplitude_fraction
                   and ((self.raw_at(i)>=self.raw_at(i-1) and self.raw_at(i)>=self.raw_at(i+1))
                        or (self.raw_at(i)<=self.raw_at(i-1) and self.raw_at(i)<=self.raw_at(i+1)))]
        position = min(extrema,key=lambda i:(abs(i-center),-abs(self.raw_at(i)-baseline))) if extrema else max(range(lo,hi+1),key=lambda i:abs(self.raw_at(i)-baseline))
        inner = self.config.sampling_hz*self.config.central_ms//1000
        outer = self.config.sampling_hz*self.config.context_ms//1000
        a,b = max(0,position-inner),min(self.received,position+inner)
        c,d = max(0,position-outer),min(self.received,position+outer)
        inside = sum(self.variation[i%self.config.input_capacity] for i in range(a,b+1))
        outside = sum(self.variation[i%self.config.input_capacity] for i in range(c,a))+sum(self.variation[i%self.config.input_capacity] for i in range(b+1,d+1))
        ratio = (inside/(b-a+1))/(outside/max(1,d-c-b+a)+1e-12)
        # QRS邻域的平均斜率低于其背景时拒绝输出；不删除该段参考心搏，漏检仍照常计分。
        if ratio<self.config.minimum_central_ratio:
            self.quality_rejections += 1
            return
        minimum = self.config.sampling_hz*self.config.refractory_ms//1000
        if self.last_position is not None and position-self.last_position<minimum:
            self.duplicate_events += 1
            return
        rr = 0 if self.last_position is None else position-self.last_position
        self.last_position = position
        self.max_event_age = max(self.max_event_age,self.received-position)
        self.pending_events.append((self.received,position,rr))

    def push(self, sample=0, valid=True, reset_n=True):
        if not reset_n:
            return self.reset()
        if not isinstance(sample,int) or not -32768<=sample<=32767:
            raise ValueError('输入必须为int16')
        if not valid:
            return []
        self.received += 1
        if self.received==0:
            self.first_sample = sample
        self.raw[self.received%self.config.input_capacity] = sample
        lowpass = self.quality_lowpass.tick(sample)
        self.variation[self.received%self.config.input_capacity] = 0. if self.previous_lowpass is None else abs(lowpass-self.previous_lowpass)
        self.previous_lowpass = lowpass
        # GQRS平滑滤波需要t+dt4+smdt附近样本；全部到齐后才恢复该步。
        while self.t+self.c.dt4+self.c.smdt+1<=self.received:
            next(self.generator)
        events,self.pending_events = self.pending_events,[]
        return events


def replay(samples, configuration=None):
    cfg = StreamConfig(**(configuration or {}))
    model = StreamDetector(cfg)
    events = []
    for sample in samples:
        events.extend(model.push(sample))
    details = dict(config=asdict(cfg),causality='BOUNDED_STREAM_NO_FUTURE_READ_NO_EOF_PADDING',
        initialization='fixed physical GQRS thresholds, no full-record learning or startup replay',
        input_buffer_samples=len(model.raw),filter_buffer_samples=len(model.qfv),peak_slots=model.c._NPEAKS,
        stale_events=model.stale_events,duplicate_events=model.duplicate_events,quality_rejections=model.quality_rejections,
        max_event_age_samples=model.max_event_age)
    return [i for _,i,_ in events],events,details
