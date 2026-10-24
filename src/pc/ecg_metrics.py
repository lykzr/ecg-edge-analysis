"""有界阶段计时；只记录调用方显式测得的阶段，不推算缺席的推理。"""
from contextlib import contextmanager
import math
import time

class StageMetrics:
    def __init__(self, clock=time.perf_counter_ns, max_stages=16):
        self.clock, self.max_stages, self.stages = clock, max_stages, {}

    def record(self, name, seconds):
        if not isinstance(name, str) or not name or len(name)>64:
            raise ValueError('阶段名须为1至64字符')
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError('计时须为有限非负秒数')
        if name not in self.stages:
            if len(self.stages)>=self.max_stages:raise BufferError('计时阶段数已满')
            self.stages[name] = dict(count=0,total_s=0.,min_s=None,max_s=0.)
        row=self.stages[name];row['count']+=1;row['total_s']+=seconds
        row['min_s']=seconds if row['min_s'] is None else min(row['min_s'],seconds)
        row['max_s']=max(row['max_s'],seconds)

    @contextmanager
    def measure(self, name):
        start=self.clock()
        try:yield
        finally:self.record(name,(self.clock()-start)/1e9)

    def summary(self):
        return {k:dict(v,mean_s=v['total_s']/v['count']) for k,v in self.stages.items()}
