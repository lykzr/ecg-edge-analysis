"""原码候选的有界原波形定位/质量确认；当前仅为软件，尚无对应RTL。"""
from collections import deque
from dataclasses import dataclass
from ecg_auto import AutoDetector
from ecg_reference import Config
from ecg_filter_reference import Biquad,coefficients


@dataclass(frozen=True)
class PeakEvent:
    emitted: int
    position: int
    rr: int
    candidate: int


class PeakDetector:
    """不读取未来、不在EOF补零；先等上下文完整再判决，原始序号不变。"""
    def __init__(self,rate=360):
        if rate not in (360,500):raise ValueError('只核验360/500Hz')
        self.rate=rate
        self.capacity=1024
        self.radius=rate*100//1000
        self.baseline_radius=rate*150//1000
        self.inner=rate*80//1000
        self.outer=rate*240//1000
        self.delay=self.radius+self.outer
        self.reset()

    def reset(self):
        self.core=AutoDetector(Config(sample_rate_hz=self.rate))
        self.raw=[0]*self.capacity
        self.variation=[0.]*self.capacity
        self.lowpass=Biquad(coefficients('lowpass',40,self.rate))
        self.previous_lowpass=None
        self.index=-1
        self.pending=deque()
        self.last_position=None
        self.last_shape=None
        self.rejected={'quality':0,'nearby':0,'duplicate':0,'flat':0}
        self.candidates=0
        self.max_pending=0
        return []

    def at(self,index,source=None):
        if not max(0,self.index-self.capacity+1)<=index<=self.index:
            raise IndexError('读取未来或过期上下文')
        return (self.raw if source is None else source)[index%self.capacity]

    def confirm(self,center):
        lo=max(0,center-self.baseline_radius);hi=center+self.baseline_radius
        outside=[self.at(i) for i in range(lo,hi+1) if abs(i-center)>self.inner]
        baseline=sorted(outside)[len(outside)//2]
        lo=max(0,center-self.radius);hi=center+self.radius
        maximum=max(abs(self.at(i)-baseline) for i in range(lo,hi+1))
        if not maximum:
            self.rejected['flat']+=1;return []
        extrema=[i for i in range(max(1,lo),hi+1)
            if abs(self.at(i)-baseline)>=maximum*.8
            and ((self.at(i)>=self.at(i-1) and self.at(i)>=self.at(i+1))
                or (self.at(i)<=self.at(i-1) and self.at(i)<=self.at(i+1)))]
        position=min(extrema,key=lambda i:(abs(i-center),-abs(self.at(i)-baseline))) if extrema else max(range(lo,hi+1),key=lambda i:abs(self.at(i)-baseline))
        a=max(0,position-self.inner);b=position+self.inner
        c=max(0,position-self.outer);d=position+self.outer
        inside=sum(self.at(i,self.variation) for i in range(a,b+1))/(b-a+1)
        outside=(sum(self.at(i,self.variation) for i in range(c,a))+sum(self.at(i,self.variation) for i in range(b+1,d+1)))/max(1,d-c-b+a)
        if inside<outside:
            self.rejected['quality']+=1;return []
        lo=max(0,position-self.inner);hi=position+self.inner
        raw=[self.at(i) for i in range(lo,hi+1)]
        positive,negative=max(raw)-baseline,baseline-min(raw)
        amplitude=max(positive,negative,1.)
        biphasic=max(0.,min(positive,negative))/amplitude
        slope=max(self.at(i,self.variation) for i in range(lo,hi+1))
        if self.last_position is not None:
            rr=position-self.last_position
            if rr<self.rate*200//1000:
                self.rejected['duplicate']+=1;return []
            if (rr<self.rate*400//1000 and self.last_shape is not None
                and slope/amplitude<.5*self.last_shape[0]/self.last_shape[1]
                and biphasic<.25 and amplitude<.75*self.last_shape[1]):
                self.rejected['nearby']+=1;return []
        rr=0 if self.last_position is None else position-self.last_position
        self.last_position=position;self.last_shape=(slope,amplitude)
        return [PeakEvent(self.index,position,rr,center)]

    def push(self,sample=0,valid=True,reset_n=True):
        if not reset_n:return self.reset()
        if not valid:return []
        if not isinstance(sample,int) or not -32768<=sample<=32767:raise ValueError('需要int16')
        self.index+=1;self.raw[self.index%self.capacity]=sample
        low=self.lowpass.tick(sample)
        self.variation[self.index%self.capacity]=0 if self.previous_lowpass is None else abs(low-self.previous_lowpass)
        self.previous_lowpass=low
        state=self.core.feed_sample(sample)
        if state.qrs_valid:
            self.candidates+=1;self.pending.append(state.qrs_sample_index)
            self.max_pending=max(self.max_pending,len(self.pending))
            if len(self.pending)>16:raise OverflowError('候选队列溢出，禁止丢弃后继续计分')
        events=[]
        while self.pending and self.pending[0]+self.delay<=self.index:
            events.extend(self.confirm(self.pending.popleft()))
        return events
