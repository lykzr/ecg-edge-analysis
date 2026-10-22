"""新候选的真实逐点边界，不用Tk替身或标注喂入检测器。"""
import sys,math,random,unittest,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if importlib.util.find_spec('wfdb') is None:
    raise unittest.SkipTest('成熟QRS候选需data/requirements_qrs.txt指定环境')
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_qrs_v5 import Detector as FilteredDetector,replay
from ecg_qrs_v4 import ShapeConfig
from wfdb.processing.qrs import GQRS

def pulses(step=360,count=6,length=2600):
    xs=[0]*length
    for k in range(count):xs[100+step*k]=20000 if k%2==0 else -20000
    return xs

class CandidateChecks(unittest.TestCase):
    def test_polarities_rr_fast_and_tail(self):
        for step,count,length in [(360,6,2600),(90,15,2200)]:
            for sign in [-1,1]:
                xs=[sign*x for x in pulses(step,count,length)]
                pos,events,_=replay(xs)
                self.assertEqual(pos,[100+step*k for k in range(count)])
                self.assertEqual([r for _,_,r in events],[0]+[step]*(count-1))
        xs=[0]*1000;xs[-4]=20000
        self.assertEqual(replay(xs)[0],[])
    def test_prefix_pause_and_reset(self):
        xs=pulses();rng=random.Random(1207)
        tail=[rng.randrange(-20000,20001) for _ in range(800)]
        expected=replay(xs)[1]
        self.assertEqual(expected,[e for e in replay(xs+tail)[1] if e[0]<len(xs)])
        m=FilteredDetector();actual=[]
        for x in xs:
            actual.extend(m.push(x))
            before=(m.received,m.core_filter.z1,m.core_filter.z2,m.last_position)
            self.assertEqual(m.push(x,valid=False),[])
            self.assertEqual(before,(m.received,m.core_filter.z1,m.core_filter.z2,m.last_position))
        self.assertEqual(actual,expected)
        m.push(reset_n=False)
        self.assertEqual(m.received,-1);self.assertEqual(m.core_filter.z1,0)
        self.assertIsNone(m.last_position)
        self.assertEqual([e for x in xs for e in m.push(x)],expected)
    def test_silence_dc_invalid_and_bounds(self):
        self.assertEqual(replay([0]*6000)[0],[])
        self.assertEqual(replay([4096]*6000)[0],[])
        self.assertEqual(replay([-4096]*6000)[0],[])
        m=FilteredDetector()
        for x in [.5,-32769,32768]:
            with self.assertRaises(ValueError):m.push(x)
        self.assertEqual(m.received,-1)
        with self.assertRaises(AssertionError):m.at(0)
        for _ in range(15000):m.push(0)
        self.assertEqual(len(m.core_raw),4096)
        self.assertEqual(len(m.raw),4096)
        self.assertEqual(len(m.qfv),1024)
        self.assertEqual(len(m.SIG_QRS),0)
        with self.assertRaises(IndexError):m.at(0)
        with self.assertRaises(AssertionError):m.at(m.received+1)
        stale=m.stale_events
        m.putann(GQRS.Annotation(10,'NORMAL',0,0))
        self.assertEqual(m.stale_events,stale+1)
        self.assertEqual(m.pending_events,[])
        with self.assertRaises(ValueError):ShapeConfig(sampling_hz=500)
    def test_connected_plateau_both_polarities(self):
        for sign in [-1,1]:
            xs=[0]*600
            knots=[(280,0),(300,10000),(307,8000),(318,9000),(335,0)]
            for (a,v),(b,w) in zip(knots,knots[1:]):
                for i in range(a,b+1):xs[i]=sign*round(v+(w-v)*(i-a)/(b-a))
            m=FilteredDetector()
            for x in xs:m.push(x)
            m.last_position=None;m.last_shape=None;m.pending_events=[]
            before=m.plateau_changes
            m.putann(GQRS.Annotation(320-m.c.dt2,'NORMAL',0,0))
            self.assertEqual(m.pending_events[-1][1],300)
            self.assertEqual(m.plateau_changes,before+1)
    def test_small_sharp_biphasic_and_broad(self):
        for pulsespec,expected in [([(100,20000,2),(200,5000,2),(560,20000,2)],[100,200,560]),
            ([(100,20000,2),(200,-19000,10),(560,20000,2)],[100,200,560]),
            ([(100,20000,2),(200,5000,4),(211,-5000,4),(560,20000,2)],[100,200,560])]:
            xs=[sum(round(a*math.exp(-.5*((i-c)/w)**2)) for c,a,w in pulsespec) for i in range(1100)]
            self.assertEqual(replay(xs)[0],expected)

if __name__=='__main__':unittest.main(verbosity=2)
