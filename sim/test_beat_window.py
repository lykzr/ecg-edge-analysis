"""切拍时序、真实缺口和训练端预处理同源检查，不训练、不读独立患者。"""
from pathlib import Path
import json
import math
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/reference'))
sys.path.insert(0, str(ROOT / 'model/prepare'))
from ecg_beat_window import BeatCutter
from ecg_signal_pipeline import SignalPipeline


class WindowTests(unittest.TestCase):
    def test_pipeline_automatic_events_keep_original_samples(self):
        from test_qrs_runtime import signal
        from ecg_qrs_runtime import AdcScale
        for rate in (360, 500):
            xs = signal(rate)
            # 同一波形以不同明确单位送入，应得到相同事件和切拍；不重新训练。
            direct = SignalPipeline(rate)
            scaled = SignalPipeline(rate, AdcScale(100000, 8192))
            events, windows = [], []
            for n, x in enumerate(xs):
                a, b = direct.push(x, sequence=n)
                c, d = scaled.push(100000 + x * 2, sequence=n)
                self.assertEqual(a, c)
                self.assertEqual(b, d)
                events += a
                windows += b
            self.assertGreater(len(windows), 4)
            for b in windows:
                self.assertEqual(b.samples, tuple(xs[b.position-b.before:b.position+math.ceil(rate*192/360)]))
                self.assertEqual(b.model_input()[0].shape, (128,))
            self.assertEqual(direct.finish()['clipped'], 0)
            self.assertFalse(scaled.finish()['cnn_inference'])

    def test_waiting_no_padding_and_exact_window(self):
        m = BeatCutter()
        output = []
        for n in range(600):
            output += m.push(n, [(n, 200, 0)] if n == 250 else (), sequence=n)
        self.assertEqual(len(output), 1)
        b = output[0]
        self.assertEqual(b.emitted, 391)
        self.assertEqual(b.samples, tuple(range(72, 392)))
        self.assertEqual(b.rr_history, ())
        self.assertIsNone(b.model_input()[1])

    def test_training_transform_equivalence_360_500(self):
        import numpy as np
        from prepare_cnn_expanded import common_window, causal_rr
        cfg = json.loads((ROOT / 'model/protocols/cnn_git_v1_protocol.json').read_text())['window']
        for rate in (360, 500):
            xs = [int(4000 * np.sin(n * .045)) for n in range(rate * 4)]
            m = BeatCutter(rate)
            windows = []
            for n, x in enumerate(xs):
                ev = [(n, rate, 0)] if n == rate + 20 else (
                    [(n, 2 * rate, rate)] if n == 2 * rate + 20 else ())
                windows.extend(m.push(x, ev))
            self.assertEqual(len(windows), 2)
            for beat in windows:
                actual, rr = beat.model_input()
                expected = common_window(np.asarray(xs) / 4096, beat.position, rate, cfg)
                np.testing.assert_array_equal(actual, expected)
                self.assertEqual(actual.shape, (128,))
                if beat.rr_samples:
                    np.testing.assert_array_equal(rr, causal_rr([rate]))

    def test_start_tail_and_gap(self):
        m = BeatCutter()
        for n in range(50):
            self.assertEqual(m.push(0, [(n, 10, 0)] if n == 20 else ()), [])
        self.assertEqual(m.startup_skipped, 1)
        with self.assertRaises(ValueError):
            m.push(0, sequence=60)
        self.assertEqual(m.index, 49)
        for n in range(50, 251):
            m.push(0, [(n, 200, 190)] if n == 250 else ())
        self.assertEqual(m.finish()['tail_skipped'], 1)
        self.assertFalse(m.finish()['padding'])

    def test_invalid_event_overflow_and_overwritten_window(self):
        m = BeatCutter(pending_capacity=1)
        for _ in range(251):
            m.push(0)
        with self.assertRaises(ValueError):
            m.push(0, [(251, 252, 0)])
        self.assertEqual(m.index, 250)
        m.push(0, [(251, 200, 0)])
        with self.assertRaises(OverflowError):
            m.push(0, [(252, 240, 40)])
        self.assertEqual(m.index, 251)
        old = BeatCutter(capacity=2048)
        for _ in range(3000):
            old.push(0)
        with self.assertRaises(IndexError):
            old.push(0, [(3000, 200, 0)])


if __name__ == '__main__':
    unittest.main()
