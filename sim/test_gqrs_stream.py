"""流式GQRS派生版：输入因果性、暂停/复位、环形容量、极性及快速心搏。"""
import importlib.util
from pathlib import Path
import random
import sys
import unittest

if importlib.util.find_spec('wfdb') is None:
    raise unittest.SkipTest('流式核心需data/requirements_qrs.txt指定的隔离环境')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/reference'))
from gqrs_stream import StreamConfig, StreamDetector, replay


def impulses(interval=360,count=7,length=3000):
    result = [0]*length
    for k in range(count):
        result[100+interval*k] = 20000 if k%2==0 else -20000
    return result


class StreamChecks(unittest.TestCase):
    def test_silence_dc_and_range(self):
        self.assertEqual(replay([0]*5000)[0],[])
        self.assertEqual(replay([4096]*5000)[0],[])
        model = StreamDetector()
        for x in (-32769,32768,.5):
            with self.assertRaises(ValueError):
                model.push(x)
        for x in (-32768,32767):
            model.push(x)
        with self.assertRaises(ValueError):
            StreamConfig(filter_capacity=300)

    def test_polarity_rr_and_fast_240_bpm(self):
        positions,events,_ = replay(impulses())
        self.assertEqual(positions,[100+360*k for k in range(7)])
        self.assertEqual([rr for _,_,rr in events],[0]+[360]*6)
        positions,events,_ = replay(impulses(interval=90,count=15,length=2200))
        self.assertEqual(positions,[100+90*k for k in range(15)])
        self.assertTrue(all(0<=emission-position<360 for emission,position,_ in events))

    def test_valid_pause_and_reset(self):
        xs = impulses()
        model = StreamDetector()
        events = []
        for x in xs:
            events.extend(model.push(x))
            before = model.received,model.t,model.c.qthr
            self.assertEqual(model.push(x,valid=False),[])
            self.assertEqual(before,(model.received,model.t,model.c.qthr))
        self.assertEqual(events,replay(xs)[1])
        model.push(reset_n=False)
        self.assertEqual(model.received,-1)
        self.assertIsNone(model.last_position)
        self.assertEqual(model.quality_rejections,0)
        self.assertEqual(model.pending_events,[])

    def test_prefix_invariance_and_no_future_reads(self):
        xs = impulses(length=4000)
        rng = random.Random(481)
        tail = [rng.randrange(-20000,20001) for _ in range(1000)]
        short = replay(xs)[1]
        long = replay(xs+tail)[1]
        self.assertEqual(short,[event for event in long if event[0]<len(xs)])
        model = StreamDetector()
        with self.assertRaises(AssertionError):
            model.at(0)
        for x in xs:
            model.push(x)
        with self.assertRaises(AssertionError):
            model.at(model.received+1)

    def test_bounded_buffers_and_no_eof_padding(self):
        model = StreamDetector()
        for _ in range(15000):
            model.push(0)
        self.assertEqual(len(model.raw),4096)
        self.assertEqual(len(model.variation),4096)
        self.assertEqual(len(model.smv),1024)
        self.assertEqual(len(model.qfv),1024)
        self.assertLessEqual(len(model.SIG_SMOOTH),10)
        self.assertLessEqual(len(model.SIG_QRS),1)
        with self.assertRaises(IndexError):
            model.raw_at(0)
        xs = [0]*1000
        xs[-4] = 20000
        self.assertEqual(replay(xs)[0],[])

    def test_physical_internal_units_roundtrip(self):
        model = StreamDetector(StreamConfig(core_units_per_mv=200))
        for value in (-1024,-300,-1,0,1,300,1023):
            scaled = (-1 if value<0 else 1)*((abs(value)*4096+100)//200)
            model.push(scaled)
            self.assertEqual(model.at(model.received),value)

    def test_selected_threshold_and_zero_energy_candidate(self):
        positions,_,_ = replay(impulses(),{'threshold':1.5})
        self.assertEqual(positions,[100+360*k for k in range(7)])
        model = StreamDetector(StreamConfig(threshold=1.5))
        for _ in range(1000):
            model.push(0)
        # 决策核心若给出零能量候选，输出侧质量检查必须拒绝，而不是产生假心搏。
        from wfdb.processing.qrs import GQRS
        model.putann(GQRS.Annotation(700,'NORMAL',0,0))
        self.assertEqual(model.pending_events,[])
        self.assertEqual(model.quality_rejections,1)


if __name__=='__main__':
    unittest.main()
