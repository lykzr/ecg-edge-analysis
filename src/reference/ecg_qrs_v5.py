"""成熟GQRS上的独立研究候选：40Hz候选低通和同极性平台定位，未上板。"""
import math
from dataclasses import replace,asdict
from ecg_qrs_v4 import ShapeConfig,ShapeDetector

class _PlateauDetector(ShapeDetector):
    def reset(self):
        self.plateau_changes=0
        return super().reset()
    def putann(self,a):
        cfg=self.config
        center=int(a.time)+self.c.dt2
        radius=cfg.sampling_hz*cfg.localization_radius_ms//1000
        br=cfg.sampling_hz*cfg.baseline_radius_ms//1000
        oldest=max(0,self.received-cfg.input_capacity+1)
        if oldest>0 and center-br<oldest:
            # 先让原实现记录过期候选，不能先在派生定位中读到已覆盖的槽。
            return super().putann(a)
        lo,hi=max(0,center-br),min(self.received,center+br)
        region=sorted(self.raw_at(i) for i in range(lo,hi+1))
        if not region:return super().putann(a)
        baseline=region[len(region)//2]
        lo,hi=max(0,center-radius),min(self.received,center+radius)
        maximum=max(abs(self.raw_at(i)-baseline) for i in range(lo,hi+1))
        extrema=[i for i in range(max(1,lo),min(self.received,hi)+1)
            if i<self.received and abs(self.raw_at(i)-baseline)>=maximum*cfg.localization_amplitude_fraction
            and ((self.raw_at(i)>=self.raw_at(i-1) and self.raw_at(i)>=self.raw_at(i+1))
                 or (self.raw_at(i)<=self.raw_at(i-1) and self.raw_at(i)<=self.raw_at(i+1)))]
        change=False
        if extrema:
            near=min(extrema,key=lambda i:(abs(i-center),-abs(self.raw_at(i)-baseline)))
            strong=max(extrema,key=lambda i:abs(self.raw_at(i)-baseline))
            v,w=self.raw_at(near)-baseline,self.raw_at(strong)-baseline
            if near!=strong and v*w>0 and abs(near-strong)<=cfg.sampling_hz*80//1000:
                sign=1 if v>0 else -1
                floor=min(sign*(self.raw_at(i)-baseline) for i in range(min(near,strong),max(near,strong)+1))
                change=floor>=.5*min(abs(v),abs(w))
        if change:
            self.plateau_changes+=1
            self.config=replace(cfg,localization_amplitude_fraction=1.0)
        try:return super().putann(a)
        finally:self.config=cfg


from ecg_filter_reference import Biquad,coefficients

class Detector(_PlateauDetector):
    def reset(self):
        self.core_filter=Biquad(coefficients('lowpass',40,self.config.sampling_hz))
        self.core_raw=[0]*self.config.input_capacity
        self.filtered_first=0
        self.filter_clipped=0
        return super().reset()
    def push(self,sample=0,valid=True,reset_n=True):
        if not reset_n:return self.reset()
        if not isinstance(sample,int) or not -32768<=sample<=32767:raise ValueError('需要int16')
        if valid:
            y=self.core_filter.tick(sample)
            y=int(math.copysign(math.floor(abs(y)+.5),y))
            self.filter_clipped+=int(not -32768<=y<=32767)
            y=min(32767,max(-32768,y))
            self.core_raw[(self.received+1)%self.config.input_capacity]=y
            if self.received==-1:self.filtered_first=y
        return super().push(sample,valid,reset_n)
    def at(self,index):
        self.raw_at(index)  # 继续执行未来/过期输入保护。
        value=self.filtered_first if index<0 else self.core_raw[index%self.config.input_capacity]
        num=value*self.config.core_units_per_mv
        mag=(abs(num)+self.config.units_per_mv//2)//self.config.units_per_mv
        return -mag if num<0 else mag


def replay(samples,configuration=None):
    model=Detector(ShapeConfig(**(configuration or {})))
    events=[]
    for value in samples:events.extend(model.push(value))
    details=dict(config=asdict(model.config),causality='BOUNDED_STREAM_NO_FUTURE_READ_NO_EOF_PADDING',
        plateau_changes=model.plateau_changes,filter_clipped=model.filter_clipped,
        stale_events=model.stale_events,duplicate_events=model.duplicate_events,
        quality_rejections=model.quality_rejections,nearby_rejections=model.nearby_rejections,
        input_buffer_samples=len(model.raw),filtered_input_samples=len(model.core_raw),
        filter_buffer_samples=len(model.qfv),peak_slots=model.c._NPEAKS,
        max_event_age_samples=model.max_event_age,
        scope='software research candidate; not qualified; not PS/RTL/board')
    return [i for _,i,_ in events],events,details
