"""评估工具的二进制解码、特殊标注与匹配边界检查。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from ecg_dataset import annotations, decode212, match_beats
from ecg_input import map_adc, calibrate
from ecg_reference import Config


def word(code, interval):
    return ((code << 10) | interval).to_bytes(2, 'little')


class FormatsAndMatching(unittest.TestCase):
    def test_amplitude(self):
        samples, clipped = map_adc([1024,1224,824,3024,-976],1024,200)
        self.assertEqual(samples,[0,4096,-4096,32767,-32768])
        self.assertEqual(clipped,2)
        self.assertEqual(map_adc([1,-1],0,2,1)[0],[1,-1])

    def test_calibration_ignores_tail_and_handles_silence(self):
        prefix=[0]*720
        first,meta=calibrate(prefix+[32767]*100,Config())
        second,_=calibrate(prefix+[-32768]*100,Config())
        self.assertEqual(first,second)
        self.assertEqual((first.initial_noise_level,first.initial_signal_level),(1,2))
        self.assertEqual(meta['samples'],720)
        with self.assertRaises(ValueError):
            calibrate([0]*10,Config())

    def test_signed212(self):
        self.assertEqual(decode212(bytes([0, 248, 255, 255, 7, 0])),
                         [[-2048, 2047], [-1, 0]])
        with self.assertRaises(ValueError):
            decode212(b'\0')

    def test_special_annotations(self):
        data = (word(28, 18) + word(63, 3) + b'abc\0' + word(1, 59)
                + word(62, 1) + word(61, 2) + word(60, 3)
                + word(59, 0) + bytes([1, 0, 2, 0]) + word(5, 1) + b'\0\0')
        self.assertEqual(annotations(data), [(18, 28), (77, 1), (65616, 5)])

    def test_ordered_matching(self):
        self.assertEqual(match_beats([100, 200], [10, 102, 300], 5),
                         ([(0, 1, 2)], [200], [10, 300]))
        self.assertEqual(match_beats([100], [95, 105], 5),
                         ([(0, 0, -5)], [], [105]))
        self.assertEqual(match_beats([], [], 54), ([], [], []))


if __name__ == '__main__':
    unittest.main()
