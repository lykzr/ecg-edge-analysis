"""无标签在线QRS形态样板：仅复核弱且背景不集中的候选，不做分类。"""
from collections import deque
from statistics import median
from dataclasses import asdict
import math
import numpy as np

def aligned_similarity(vector,templates):
    if not templates:return 0.
    a=np.asarray(vector);n=len(a);ca=np.r_[0.,np.cumsum(a*a)];best=0.
    for template in templates:
        t=np.asarray(template);ct=np.r_[0.,np.cumsum(t*t)];corr=np.correlate(a,t,mode="full")
        for shift in range(-10,11):
            alo,ahi=max(0,shift),min(n,n+shift);tlo,thi=max(0,-shift),min(n,n-shift)
            denom=(ca[ahi]-ca[alo])*(ct[thi]-ct[tlo])
            score=corr[n-1+shift]/math.sqrt(max(1e-24,denom))
            best=max(best,float(score))
    return best

from .recovery import Detector as Original
from ecg_qrs_v4 import ShapeConfig
class Detector(Original):
    def reset(self):
        self.templates=[];self.energies=deque(maxlen=8);self.amplitudes=deque(maxlen=8)
        self.template_rejections=0;self.width_rejections=0;self.last_width=None;self.audit=[]
        return super().reset()
    def putann(self,ann):
        previous_width=self.last_width
        energy=int(self.qfv_at(int(ann.time)+self.c.dt2))
        previous,shape=self.last_position,self.last_shape;count=len(self.pending_events)
        super().putann(ann)
        if len(self.pending_events)==count:return
        cfg=self.config;_,pos,_=self.pending_events[-1]
        inner=cfg.sampling_hz*80//1000;outer=cfg.sampling_hz*240//1000
        a,b=max(0,pos-inner),min(self.received,pos+inner)
        c,d=max(0,pos-outer),min(self.received,pos+outer)
        inside=sum(self.variation[i%cfg.input_capacity] for i in range(a,b+1))/(b-a+1)
        outside=(sum(self.variation[i%cfg.input_capacity] for i in range(c,a))+sum(self.variation[i%cfg.input_capacity] for i in range(b+1,d+1)))/max(1,d-c-b+a)
        amplitude=self.last_shape[1]
        vector=[self.raw_at(max(0,i)) for i in range(pos-inner,pos+inner+1)]
        mean=sum(vector)/len(vector);vector=[v-mean for v in vector]
        norm=math.sqrt(sum(v*v for v in vector));vector=[v/max(1.,norm) for v in vector]
        correlations=[sum(v*w for v,w in zip(vector,t)) for t in self.templates]
        unshifted=max(correlations,default=0.)
        similarity=aligned_similarity(vector,self.templates)
        br=cfg.sampling_hz*150//1000
        flank=[self.raw_at(i) for i in range(max(0,pos-br),a)]+[self.raw_at(i) for i in range(b+1,min(self.received,pos+br)+1)]
        baseline=median(flank) if flank else self.raw_at(pos)
        raw=[self.raw_at(i) for i in range(a,b+1)]
        positive,negative=max(raw)-baseline,baseline-min(raw)
        amp=max(positive,negative,1.);biphasic=max(0,min(positive,negative))/amp
        v=self.raw_at(pos)-baseline;sign=1 if v>=0 else -1;half=abs(v)/2
        left=right=pos
        while left>max(0,pos-br) and sign*(self.raw_at(left-1)-baseline)>=half:left-=1
        while right<min(self.received,pos+br) and sign*(self.raw_at(right+1)-baseline)>=half:right+=1
        width=right-left+1
        suspect=(previous is not None and previous_width is not None and pos-previous<cfg.sampling_hz*cfg.inspect_ms//1000 and width>previous_width/cfg.slope_fraction and amp<cfg.amplitude_rescue_fraction*shape[1] and biphasic<cfg.biphasic_fraction)
        if suspect and similarity<.8:
            self.pending_events.pop();self.last_position,self.last_shape=previous,shape
            self.width_rejections+=1
            self.audit.append(dict(index=pos,reason='wide_unfamiliar',similarity=similarity,width=width,previous_width=previous_width))
            return
        learned=len(self.energies)==8
        low=(learned and energy<.5*median(self.energies) and inside<2*outside)
        if self.templates and low and similarity<.8:
            self.pending_events.pop();self.last_position,self.last_shape=previous,shape
            self.last_width=previous_width
            self.template_rejections+=1;self.audit.append(dict(index=pos,reason="weak_unfamiliar",similarity=similarity));return
        high=not learned or (inside>=2*outside and energy>=.5*median(self.energies))
        if high:
            if unshifted>=.9:
                k=max(range(len(correlations)),key=lambda k:correlations[k]);sign=1
                t=[.875*w+.125*sign*v for v,w in zip(vector,self.templates[k])]
                n=math.sqrt(sum(v*v for v in t));self.templates[k]=[v/max(1e-12,n) for v in t]
            elif similarity<.9 and len(self.templates)<8:self.templates.append(vector)
        self.last_width=width
        self.energies.append(energy);self.amplitudes.append(amplitude)
def replay(samples,configuration=None):
    m=Detector(ShapeConfig(**(configuration or {})));events=[]
    for x in samples:events.extend(m.push(x))
    return [i for _,i,_ in events],events,dict(config=asdict(m.config),templates=len(m.templates),
        template_rejections=m.template_rejections,width_rejections=m.width_rejections,audit=m.audit,causality='BOUNDED_NO_LABELS_NO_FUTURE_NO_EOF_PADDING')
