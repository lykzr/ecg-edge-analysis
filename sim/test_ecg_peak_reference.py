"""候选峰原型的边界、极性、RR与暂停/复位检查；无需板卡。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/reference'))
from ecg_peak_reference import PeakDetector


def replay(samples, idle=False):
    model = PeakDetector()
    events = []
    for sample in samples:
        state = model.tick(sample)
        if state.qrs_valid:
            events.append((state.qrs_sample_index,state.rr_interval_samples))
        if idle:
            state = model.tick(sample,valid=False)
            assert not state.qrs_valid
    return model,events


class PeakChecks(unittest.TestCase):
    def test_long_silence(self):
        _,events=replay([0]*5000)
        self.assertEqual(events,[])

    def test_positive_negative_and_rr(self):
        samples=[0]*100
        for i in range(16):
            samples += [20000 if i%2==0 else -20000]+[0]*359
        model,events=replay(samples)
        self.assertEqual(events,[(100+360*i,0 if i==0 else 360) for i in range(16)])
        self.assertEqual(replay(samples,True)[1],events)
        model.tick(reset_n=False)
        self.assertEqual(model.index,-1)
        self.assertIsNone(model.last_qrs)
        self.assertEqual(model.tick(0).integrated_energy,0)

    def test_refractory(self):
        samples=[0]*700
        for i in (100,150,500):
            samples[i]=20000
        _,events=replay(samples)
        self.assertEqual([i for i,_ in events],[100,500])

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            PeakDetector().tick(32768)


if __name__=='__main__':
    unittest.main()
