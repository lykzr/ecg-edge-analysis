"""原波形确认的软件边界；不代替标注回归或硬件仿真。"""
import math
from pathlib import Path
import random
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_peak import PeakDetector


def gaussian(pulses,length):
    return [sum(round(a*math.exp(-.5*((i-c)/w)**2)) for c,a,w in pulses) for i in range(length)]


def run(samples,rate=360):
    detector=PeakDetector(rate);events=[]
    for x in samples:events.extend(detector.push(x))
    return events,detector


class PeakChecks(unittest.TestCase):
    def test_raw_peak_position_polarity_and_rr(self):
        for rate in (360,500):
            centers=[100+rate*i for i in range(7)]
            xs=gaussian([(c,20000 if i%2==0 else -20000,2) for i,c in enumerate(centers)],100+rate*7)
            for values in (xs,[-x for x in xs]):
                events,detector=run(values,rate)
                self.assertEqual([e.position for e in events],centers[2:])
                self.assertEqual([e.rr for e in events],[0]+[rate]*4)
                self.assertTrue(all(e.emitted>=e.position for e in events))
                self.assertLessEqual(detector.max_pending,16)

    def test_weak_broad_following_wave(self):
        pulses=[(100+360*i,20000,2) for i in range(7)]+[(200+360*i,-7000,8) for i in range(7)]
        events,_=run(gaussian(pulses,2700))
        self.assertEqual([e.position for e in events],[820,1180,1540,1900,2260])

    def test_constant_and_tail_not_padded(self):
        for value in (-32768,0,2048,32767):self.assertEqual(run([value]*3000)[0],[])
        # 留够核心积分峰确认，仍不给外围质量窗口足够的尾部上下文。
        xs=[0]*1500;xs[-80]=20000
        events,detector=run(xs)
        self.assertEqual(events,[])
        self.assertTrue(detector.pending)

    def test_prefix_causality_pause_and_reset(self):
        xs=gaussian([(100+360*i,20000,2) for i in range(6)],2200)
        old,_=run(xs);rng=random.Random(3107)
        new,_=run(xs+[rng.randrange(-10000,10001) for _ in range(700)])
        self.assertEqual(old,[e for e in new if e.emitted<len(xs)])
        d=PeakDetector();events=[]
        for x in xs:
            events.extend(d.push(x));state=(d.index,len(d.pending),d.last_position)
            self.assertEqual(d.push(32767,valid=False),[])
            self.assertEqual(state,(d.index,len(d.pending),d.last_position))
        self.assertEqual(events,old)
        d.push(reset_n=False);again=[]
        for x in xs:again.extend(d.push(x))
        self.assertEqual(old,again)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):PeakDetector(250)
        for x in (32768,-32769,1.5):
            with self.assertRaises(ValueError):PeakDetector().push(x)

    def test_large_broad_and_small_biphasic_candidates_survive(self):
        regular=[(100+360*i,20000,2) for i in range(6)]
        for extra,position in [([(920,-19000,10)],920), ([(920,5000,4),(931,-5000,4)],931)]:
            events,_=run(gaussian(regular+extra,2500))
            self.assertEqual([e.position for e in events],[820,position,1180,1540,1900])

    def test_fast_true_beats_not_removed_as_following_waves(self):
        xs=[0]*3100
        for i in range(30):xs[100+90*i]=20000 if i%2==0 else -20000
        events,_=run(xs)
        self.assertEqual([e.position for e in events],[100+90*i for i in range(7,30)])
        self.assertEqual([e.rr for e in events],[0]+[90]*22)


if __name__=='__main__':unittest.main()
