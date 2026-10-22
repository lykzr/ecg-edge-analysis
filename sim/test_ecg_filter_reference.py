"""因果滤波参考的独立差分方程、稳定性、频率、流式状态与饱和检查。"""
import cmath
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/reference'))
from ecg_filter_reference import Biquad, Filter, coefficients


class FilterChecks(unittest.TestCase):
    def test_500hz_independent_equations_and_notch50(self):
        values = coefficients('notch',50,500,30)
        model = Biquad(values)
        b0,b1,b2,a1,a2 = values
        x1=x2=y1=y2=0.
        ys = []
        for i in range(10000):
            x = 4096*math.sin(2*math.pi*50*i/500)
            expected = b0*x+b1*x1+b2*x2-a1*y1-a2*y2
            actual = model.tick(x)
            self.assertAlmostEqual(actual,expected,places=7)
            ys.append(actual)
            x2,x1,y2,y1 = x1,x,y1,expected
        self.assertLess(max(map(abs,ys[5000:])),1e-7)
        self.assertLess(abs(model.response(50,500)),1e-10)

    def test_independent_direct_form(self):
        for kind,f,q in [('highpass',.5,math.sqrt(.5)),('lowpass',40,math.sqrt(.5)),('notch',60,30)]:
            values = coefficients(kind,f,q=q)
            model = Biquad(values)
            b0,b1,b2,a1,a2 = values
            x1=x2=y1=y2=0.
            for i in range(4000):
                x = 1000 if i==0 else 400*math.sin(i*.27)
                expected = b0*x+b1*x1+b2*x2-a1*y1-a2*y2
                self.assertAlmostEqual(model.tick(x),expected,places=6)
                x2,x1,y2,y1 = x1,x,y1,expected
            discriminant = cmath.sqrt(a1*a1-4*a2)
            self.assertTrue(all(abs(p)<1 for p in ((-a1+discriminant)/2,(-a1-discriminant)/2)))

    def test_response(self):
        hp = Biquad(coefficients('highpass',.5))
        lp = Biquad(coefficients('lowpass',40))
        nt = Biquad(coefficients('notch',60,q=30))
        self.assertLess(abs(hp.response(0)),1e-8)
        self.assertAlmostEqual(abs(hp.response(.5)),math.sqrt(.5),places=8)
        self.assertAlmostEqual(abs(lp.response(40)),math.sqrt(.5),places=8)
        self.assertLess(abs(nt.response(60)),1e-10)
        self.assertGreater(abs(nt.response(10)),.999)
        self.assertGreater(abs(nt.response(30)),.999)

    def test_streaming_reset_and_causality(self):
        xs = [int(10000*math.sin(i*.23)) for i in range(2000)]
        model = Filter('bandpass_notch')
        first = [model.tick(x) for x in xs[:725]]
        second = [model.tick(x) for x in xs[725:]]
        model.reset()
        self.assertEqual(first+second,[model.tick(x) for x in xs])
        alternate = Filter('bandpass_notch')
        self.assertEqual(first,[alternate.tick(x) for x in xs[:725]])
        self.assertEqual(Filter('raw').tick(-32768),-32768)
        raw = Filter('raw')
        self.assertEqual(raw.tick(40000),32767)
        self.assertEqual(raw.tick(-40000),-32768)
        self.assertEqual(raw.clipped,2)

    def test_synthetic_mains_and_dc(self):
        # 60秒输入，舍弃前10秒仅用于滤波器稳态验证，不用于真实记录打分。
        model = Filter('notch')
        ys = [model.tick(4096*math.sin(2*math.pi*60*i/360)) for i in range(21600)]
        self.assertLess(math.sqrt(sum(y*y for y in ys[3600:])/len(ys[3600:])),1)
        for mains in (50,60):
            model = Filter('notch',notch_hz=mains)
            ys = [model.tick(4096*math.sin(2*math.pi*mains*i/360)) for i in range(7200)]
            self.assertLess(max(map(abs,ys[3600:])),2)
        model = Filter('bandpass')
        ys = [model.tick(4096) for _ in range(7200)]
        self.assertEqual(max(map(abs,ys[3600:])),0)


if __name__ == '__main__':
    unittest.main()
