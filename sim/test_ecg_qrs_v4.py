"""v4近邻宽波抑制及真实候选救援的合成边界检查。"""
import importlib.util
import math
from pathlib import Path
import random
import sys
import unittest

if importlib.util.find_spec('wfdb') is None:
    raise unittest.SkipTest('v4需data/requirements_qrs.txt指定的隔离环境')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/reference'))
from ecg_qrs_v4 import ShapeConfig, ShapeDetector, replay


def gaussian(pulses,length):
    return [sum(round(a*math.exp(-.5*((i-c)/w)**2)) for c,a,w in pulses) for i in range(length)]


class ShapeChecks(unittest.TestCase):
    def test_broad_weak_following_wave_both_polarities(self):
        xs=gaussian([(100,20000,2),(200,-7000,8),(460,20000,2),
                     (560,-7000,8),(820,20000,2),(920,-7000,8)],1400)
        self.assertEqual(replay(xs)[0],[100,460,820])
        self.assertEqual(replay([-x for x in xs])[0],[100,460,820])

    def test_large_broad_and_small_biphasic_rescue(self):
        large=gaussian([(100,20000,2),(200,-19000,10),(560,20000,2)],1100)
        small=gaussian([(100,20000,2),(200,5000,4),(211,-5000,4),(560,20000,2)],1100)
        self.assertEqual(replay(large)[0],[100,200,560])
        self.assertEqual(replay(small)[0],[100,200,560])
        # 幅值小但仍很陡的真候选不能仅因绝对斜率小而被当作宽波。
        small_sharp=gaussian([(100,20000,2),(200,5000,2),(560,20000,2)],1100)
        self.assertEqual(replay(small_sharp)[0],[100,200,560])

    def test_fast_true_beats_and_rr(self):
        xs=[0]*2200
        for k in range(15):
            xs[100+90*k]=20000 if k%2==0 else -20000
        positions,events,_=replay(xs)
        self.assertEqual(positions,[100+90*k for k in range(15)])
        self.assertEqual([r for _,_,r in events],[0]+[90]*14)

    def test_prefix_pause_and_reset(self):
        xs=gaussian([(100,20000,2),(200,-7000,8),(560,20000,2)],1200)
        rng=random.Random(421)
        longer=xs+[rng.randrange(-10000,10001) for _ in range(700)]
        self.assertEqual(replay(xs)[1],[e for e in replay(longer)[1] if e[0]<len(xs)])
        model=ShapeDetector()
        events=[]
        for x in xs:
            events.extend(model.push(x))
            state=(model.received,model.last_position,model.last_shape)
            self.assertEqual(model.push(x,valid=False),[])
            self.assertEqual(state,(model.received,model.last_position,model.last_shape))
        self.assertEqual(events,replay(xs)[1])
        model.push(reset_n=False)
        self.assertIsNone(model.last_shape)
        self.assertIsNone(model.last_position)
        self.assertEqual(model.nearby_rejections,0)

    def test_config_and_tail(self):
        with self.assertRaises(ValueError):
            ShapeConfig(slope_fraction=0)
        xs=[0]*1000
        xs[-3]=20000
        self.assertEqual(replay(xs)[0],[])


if __name__=='__main__':
    unittest.main()
