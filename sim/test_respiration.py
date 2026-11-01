"""受控呼吸信号验证；不替代真实呼吸参考标注。"""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pc'))
from ecg_respiration import RespirationFilter


class RespirationTests(unittest.TestCase):
    def test_offset_initialization_and_gap(self):
        f = RespirationFilter()
        self.assertEqual([f.process(i, 410000) for i in range(1000)], [0.] * 1000)
        self.assertEqual(f.process(1100, 420000), 0.)
        self.assertEqual(RespirationFilter().process(0, -123456), 0.)

    def test_respiration_preserved_noise_suppressed_and_chunks_identical(self):
        def signal(hz):
            return [410000 + 1000*math.sin(2*math.pi*hz*i/500) for i in range(30000)]
        def run(values, chunk):
            f = RespirationFilter()
            return [f.process(i, values[i]) for start in range(0,len(values),chunk)
                    for i in range(start,min(start+chunk,len(values))) ]
        values = signal(.25)
        clean = run(values, len(values))
        self.assertEqual(clean, run(values, 137))
        rms = lambda a: math.sqrt(sum(v*v for v in a[10000:])/len(a[10000:]))
        self.assertGreater(rms(clean), 650)
        self.assertLess(rms(run(signal(50), 137)), 1)
        self.assertLess(rms(run(signal(5), 137)), 25)


if __name__ == '__main__':
    unittest.main()
