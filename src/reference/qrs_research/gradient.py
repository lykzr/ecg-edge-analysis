"""独立因果梯度实现：参考NeuroKit默认100/750ms自适应梯度思路。

来源与差异见docs/qrs_research.md、此目录provenance.json；不是原函数数值复现。
原函数整段平均宽度改为已接受区域的有界中位数，不读整段未来。
"""
from collections import deque
from statistics import median
from ecg_filter_reference import Biquad,coefficients

class Detector:
    def __init__(self,rate=360):
        if rate not in (360,500):raise ValueError('仅360/500Hz研究输入')
        self.rate=rate;self.capacity=4096
        self.h1=round(rate*.1)//2;self.h2=round(rate*.75)//2
        self.w1=2*self.h1+1;self.w2=2*self.h2+1
        self.delay=1+self.h1+self.h2
        self.reset()
    def reset(self):
        self.index=-1;self.raw=[0]*self.capacity;self.filtered=[0.]*self.capacity;self.smooth=[0.]*self.capacity
        self.hp=Biquad(coefficients('highpass',.5,self.rate));self.lp=Biquad(coefficients('lowpass',40,self.rate))
        self.gwindow=deque([0.]*self.h1);self.gsum=0.
        self.bwindow=deque([0.]*self.h2);self.bsum=0.
        self.active=None;self.widths=deque(maxlen=8);self.last=None
        self.short=self.long=self.duplicates=0;self.max_age=0
        return []
    def at(self,i,source=None):
        if not max(0,self.index-self.capacity+1)<=i<=self.index:raise IndexError('读取未来或过期')
        return (self.raw if source is None else source)[i%self.capacity]
    def confirm(self,start,end):
        width=end-start
        minimum=.4*median(self.widths) if self.widths else self.rate*.032
        if width<minimum:self.short+=1;return []
        if width>self.rate*.5:self.long+=1;return []
        br=self.rate*150//1000
        flank=[self.at(i) for i in range(max(0,start-br),start)]+[self.at(i) for i in range(end+1,min(self.index,end+br)+1)]
        baseline=median(flank) if flank else self.at(start)
        extrema=[i for i in range(max(1,start),min(end,self.index-1)+1) if
            (self.at(i)>=self.at(i-1) and self.at(i)>=self.at(i+1)) or
            (self.at(i)<=self.at(i-1) and self.at(i)<=self.at(i+1))]
        if not extrema:return []
        pos=max(extrema,key=lambda i:(abs(self.at(i)-baseline),-abs(i-(start+end)/2)))
        if self.last is not None and pos-self.last<self.rate*240//1000:self.duplicates+=1;return []
        rr=0 if self.last is None else pos-self.last;self.last=pos
        self.widths.append(width);self.max_age=max(self.max_age,self.index-pos)
        return [(self.index,pos,rr)]
    def push(self,sample=0,valid=True,reset_n=True):
        if not reset_n:return self.reset()
        if not isinstance(sample,int) or not -32768<=sample<=32767:raise ValueError('需要int16')
        if not valid:return []
        self.index+=1;n=self.index;self.raw[n%self.capacity]=sample
        if n==0:
            self.hp.z1=-self.hp.values[0]*sample;self.hp.z2=self.hp.values[2]*sample
        self.filtered[n%self.capacity]=self.lp.tick(self.hp.tick(sample))
        if n==0:return []
        old=self.at(max(0,n-2),self.filtered)
        grad=abs((self.at(n,self.filtered)-old)/2)
        self.gwindow.append(grad);self.gsum+=grad
        if len(self.gwindow)>self.w1:self.gsum-=self.gwindow.popleft()
        if len(self.gwindow)<self.w1:return []
        s=n-1-self.h1;smooth=self.gsum/self.w1;self.smooth[s%self.capacity]=smooth
        self.bwindow.append(smooth);self.bsum+=smooth
        if len(self.bwindow)>self.w2:self.bsum-=self.bwindow.popleft()
        if len(self.bwindow)<self.w2:return []
        c=s-self.h2;threshold=1.5*max(0.,self.bsum/self.w2)
        on=self.at(c,self.smooth)>max(1e-9,threshold)
        if self.active==-1:
            if not on:self.active=None
            return []
        if on and self.active is None:self.active=c
        elif not on and self.active is not None:
            start=self.active;self.active=None
            return self.confirm(start,c)
        if self.active is not None and c-self.active>self.rate:
            # 超长段进入拒绝状态，仍保存输入；不把持续伪迹反复切成新心拍。
            self.long+=1;self.active=-1
        return []

def replay(samples,configuration=None):
    cfg=configuration or {};m=Detector(cfg.get('sampling_hz',360));events=[]
    for x in samples:events.extend(m.push(x))
    return [i for _,i,_ in events],events,dict(rate=m.rate,delay=m.delay,max_age=m.max_age,
        short=m.short,long=m.long,duplicates=m.duplicates,
        causality='BOUNDED_CENTERED_CONTEXT_NO_FUTURE_READ_NO_EOF_PADDING')
