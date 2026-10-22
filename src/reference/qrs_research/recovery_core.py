# 独立候选：先验证输出后更新RR/T标记；原MIT许可和第三方来源见正式gqrs_core.py。
# 派生自WFDB 4.3.1 GQRS.gqrs；Copyright (c) 2016 MIT Laboratory for Computational Physiology
# MIT许可全文见src/third_party/wfdb_license.txt；原实现及生成差异见src/third_party/gqrs_provenance.json。
# 改动：逐步yield；去掉EOF补样；每50ms检查已成熟峰队列；循环有界；清理诊断列表。
from wfdb.processing.qrs import GQRS

def steps(self, from_sample=0):
    q0 = None
    q1 = 0
    q2 = 0
    rr = None
    rrd = None
    rt = None
    rtd = None
    rtdmin = None
    p = None
    q = None
    r = None
    tw = None
    last_peak = from_sample
    last_qrs = from_sample
    self.SIG_SMOOTH = []
    self.SIG_QRS = []

    def add_peak(peak_time, peak_amp, peak_type):
        p = self.current_peak.next_peak
        p.time = peak_time
        p.amp = peak_amp
        p.type = peak_type
        self.current_peak = p
        p.next_peak.amp = 0

    def peaktype(p):
        if p.type:
            return p.type
        else:
            a = p.amp
            t0 = p.time - self.c.rrmin
            t1 = p.time + self.c.rrmin
            if t0 < 0:
                t0 = 0
            pp = p.prev_peak
            while t0 < pp.time and pp.time < pp.next_peak.time:
                if pp.amp == 0:
                    break
                if a < pp.amp and peaktype(pp) == 1:
                    p.type = 2
                    return p.type
                pp = pp.prev_peak
            pp = p.next_peak
            while pp.time < t1 and pp.time > pp.prev_peak.time:
                if pp.amp == 0:
                    break
                if a < pp.amp and peaktype(pp) == 1:
                    p.type = 2
                    return p.type
                pp = pp.next_peak
            p.type = 1
            return p.type

    def find_missing(r, p):
        if r is None or p is None:
            return None
        minrrerr = p.time - r.time
        s = None
        q = r.next_peak
        while q.time < p.time:
            if peaktype(q) == 1:
                rrtmp = q.time - r.time
                rrerr = rrtmp - self.c.rrmean
                if rrerr < 0:
                    rrerr = -rrerr
                if rrerr < minrrerr:
                    minrrerr = rrerr
                    s = q
            q = q.next_peak
        return s
    r = None
    next_minute = 0
    minutes = 0
    while True:
        yield self.t
        self.qf()
        q0 = self.qfv_at(self.t)
        q1 = self.qfv_at(self.t - 1)
        q2 = self.qfv_at(self.t - 2)
        new_peak = q1 > self.c.pthr and q2 < q1 and (q1 >= q0) and (self.t > self.c.dt4)
        if new_peak:
            add_peak(self.t - 1, q1, 0)
            last_peak = self.t - 1
        if new_peak or self.t % self.probe_samples == 0:
            drain_count = 0
            p = self.current_peak.next_peak
            while p.time < self.t - self.c.rtmax and drain_count < self.c._NPEAKS:
                drain_count += 1
                if p.time >= self.annot.time + self.c.rrmin and peaktype(p) == 1:
                    if p.amp > self.c.qthr:
                        rr = p.time - self.annot.time
                        q = find_missing(r, p)
                        if rr > 1.66 * self.c.rrmean and (q is not None):
                            p = q
                            rr = p.time - self.annot.time
                            self.annot.subtype = 1
                        # 验证候选在前，拒绝者不消耗RR/不把后续真波标成T。
                        if self.state == 'RUNNING':
                            n_before = len(self.pending_events)
                            provisional = GQRS.Annotation(p.time-self.c.dt2, 'NORMAL', 0, 0)
                            self.putann(provisional)
                            if len(self.pending_events) == n_before:
                                p.type = 2
                                p = p.next_peak
                                continue
                        rrd = rr - self.c.rrmean
                        if rrd < 0:
                            rrd = -rrd
                        self.c.rrdev += rrd - self.c.rrdev >> 3
                        if rrd > self.c.rrinc:
                            rrd = self.c.rrinc
                        if rr > self.c.rrmean:
                            self.c.rrmean += rrd
                        else:
                            self.c.rrmean -= rrd
                        if p.amp > self.c.qthr * 4:
                            self.c.qthr += 1
                        elif p.amp < self.c.qthr:
                            self.c.qthr -= 1
                        if self.c.qthr > self.c.pthr * 20:
                            self.c.qthr = self.c.pthr * 20
                        last_qrs = p.time
                        if self.state == 'RUNNING':
                            self.annot.time = p.time - self.c.dt2
                            self.annot.type = 'NORMAL'
                            qsize = int(p.amp * 10.0 / self.c.qthr)
                            if qsize > 127:
                                qsize = 127
                            self.annot.num = qsize
                            # 已在更新状态前验证并输出，不重复调用。
                            self.annot.time += self.c.dt2
                        tw = None
                        rtdmin = self.c.rtmean
                        q = p.next_peak
                        while q.time > self.annot.time:
                            rt = q.time - self.annot.time - self.c.dt2
                            if rt < self.c.rtmin:
                                q = q.next_peak
                                continue
                            if rt > self.c.rtmax:
                                break
                            rtd = rt - self.c.rtmean
                            if rtd < 0:
                                rtd = -rtd
                            if rtd < rtdmin:
                                rtdmin = rtd
                                tw = q
                            q = q.next_peak
                        if tw is not None:
                            tmp_time = tw.time - self.c.dt2
                            tann = GQRS.Annotation(tmp_time, 'TWAVE', 1 if tmp_time > self.annot.time + self.c.rtmean else 0, rtdmin)
                            rt = tann.time - self.annot.time
                            self.c.rtmean += rt - self.c.rtmean >> 4
                            if self.c.rtmean > self.c.rtmax:
                                self.c.rtmean = self.c.rtmax
                            elif self.c.rtmean < self.c.rtmin:
                                self.c.rtmean = self.c.rrmin
                            # T波最终由原波形近邻确认，不在能量域提前排除后续心拍。
                        r = p
                        q = None
                        self.annot.subtype = 0
                    elif self.t - last_qrs > self.c.rrmax and self.c.qthr > self.c.qthmin:
                        self.c.qthr -= self.c.qthr >> 4
                p = p.next_peak
        elif self.t - last_peak > self.c.rrmax and self.c.pthr > self.c.pthmin:
            self.c.pthr -= self.c.pthr >> 4
        self.t += 1
        if self.t >= next_minute:
            next_minute += self.c.spm
            minutes += 1
            if minutes >= 60:
                minutes = 0
        self.SIG_SMOOTH.clear()
        self.SIG_QRS.clear()
