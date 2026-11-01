"""PC显示链路与固定增益、跨块状态、频率抑制验证。"""
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src/pc'), str(ROOT/'src/reference')]
from ecg_display import EcgDisplayFilter
from ecg_bridge_capture import NominalConverter


class DisplayTests(unittest.TestCase):
    def test_dc_and_gap_reset(self):
        f = EcgDisplayFilter()
        for i in range(1000):
            self.assertEqual(f.process(i, -1300000)['ecg_display_mv'], 0.)
        self.assertEqual(f.process(1005, -1200000)['ecg_baseline_mv'], 0.)

    def test_scale_and_baseline_equal_existing_input_before_quantization(self):
        f, existing = EcgDisplayFilter(), NominalConverter(dc_block=True)
        for i in range(10000):
            code = round(-1300000 + 60000 * math.sin(2*math.pi*2*i/500))
            result = f.process(i, code)
            existing.convert((0,code))
            self.assertAlmostEqual(result['ecg_baseline_mv'], existing.output_mv, places=11)
            self.assertAlmostEqual(result['ecg_baseline_mv'], result['ecg_baseline_code']*2420/(6*8388607))

    def test_gain_noise_rejection_and_offset_invariance(self):
        def run(hz, amplitude, offset, chunk):
            f = EcgDisplayFilter()
            return [f.process(i,offset+amplitude*math.sin(2*math.pi*hz*i/500))['ecg_display_code']
                    for start in range(0,15000,chunk) for i in range(start,min(start+chunk,15000))]
        base = run(5,1000,0,15000)
        self.assertEqual(base, run(5,1000,0,137))
        offset = run(5,1000,-1300000,137)
        self.assertLess(max(abs(a-b) for a,b in zip(base,offset)),1e-6)
        double = run(5,2000,0,137)
        self.assertLess(max(abs(2*a-b) for a,b in zip(base,double)),1e-6)
        rms = lambda a: math.sqrt(sum(x*x for x in a[5000:])/len(a[5000:]))
        self.assertGreater(rms(base),690)
        self.assertLess(rms(run(50,1000,0,137)),1)


if __name__ == '__main__':
    unittest.main()
