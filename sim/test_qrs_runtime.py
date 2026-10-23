"""运行时等价、有限状态、序号拒绝及500Hz物理映射检查。"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/reference'))
from qrs_research import replay
from ecg_qrs_runtime import ResearchRuntime, InputRuntime, RateAdapter, AdcScale


def signal(rate=360, seconds=10):
    values = [0] * (seconds * rate)
    for p in range(rate, len(values) - rate, rate):
        for j in range(-8, 9):
            values[p + j] = (1 if p // rate % 2 else -1) * (16000 - 1800 * abs(j))
    return values


class RuntimeTests(unittest.TestCase):
    def test_frozen_replay_equivalence_and_tail(self):
        xs = signal()
        expected = replay(xs)[1]
        self.assertGreater(len(expected), 4)
        model = ResearchRuntime()
        actual = [e for n, x in enumerate(xs) for e in model.push(x, sequence=n)]
        self.assertEqual(actual, expected)
        self.assertEqual(model.finish()['tail_pending'], replay(xs)[2]['tail_pending'])
        self.assertEqual(model.finish(), model.finish())
        with self.assertRaises(RuntimeError):
            model.push(0)

    def test_prefix_invariance(self):
        xs = signal()
        def run(seq):
            m = ResearchRuntime()
            return [e for x in seq for e in m.push(x)]
        cutoff = 2100
        self.assertEqual(run(xs[:cutoff]), [e for e in run(xs) if e[0] < cutoff])

    def test_sequence_pause_reset_and_range(self):
        m = ResearchRuntime()
        self.assertEqual(m.push(0, valid=False), [])
        self.assertEqual(m.index, -1)
        for bad in (1, -1, True):
            with self.assertRaises(ValueError):
                m.push(0, sequence=bad)
            self.assertEqual(m.index, -1)
        for bad in (32768, -32769, 1., True):
            with self.assertRaises(ValueError):
                m.push(bad)
        m.push(0, sequence=0)
        m.push(reset_n=False)
        self.assertEqual(m.index, -1)
        with self.assertRaises(IndexError):
            m.at(0)

    def test_bounded_state_and_zero_input(self):
        m = ResearchRuntime()
        for x in signal(seconds=40):
            m.push(x)
        self.assertEqual(len(m.raw), 4096)
        self.assertEqual(len(m.primary.audit), 0)
        self.assertLessEqual(len(m.primary.templates), 8)
        self.assertLessEqual(len(m.pending), 32)
        self.assertLessEqual(len(m.cache), 32)
        self.assertEqual(len(m.secondary.raw), 4096)
        z = ResearchRuntime()
        self.assertEqual([e for _ in range(6000) for e in z.push(0)], [])

    def test_rate_adapter_constant_count_and_position(self):
        m = RateAdapter(500)
        values = [y for _ in range(5000) for _, y in m.push(1234)]
        self.assertEqual(len(values), 3600)
        self.assertEqual(set(values), {1234})
        self.assertEqual(m.source_index(360), 470)
        self.assertEqual(len(m.history), 61)
        for rate in (0, 250, 1000):
            with self.assertRaises(ValueError):
                RateAdapter(rate)

    def test_500hz_impulse_localization_and_rr(self):
        m = InputRuntime(500)
        events = [e for i, x in enumerate(signal(500)) for e in m.push(x, sequence=i)]
        self.assertGreater(len(events), 4)
        self.assertTrue(all(abs(p - round(p / 500) * 500) <= 5 for _, p, _ in events))
        self.assertTrue(all(abs(rr - 500) <= 5 for _, _, rr in events[1:]))
        self.assertTrue(all(emitted >= p for emitted, p, _ in events))
        self.assertEqual(m.finish()['fir_delay_source_samples'], 30)

    def test_amplitude_rounding_saturation_and_input_mapping(self):
        m = AdcScale(1024, 200)
        self.assertEqual(m.convert(1224), (4096, False))
        self.assertEqual(m.convert(824), (-4096, False))
        self.assertEqual(m.convert(99999), (32767, True))
        self.assertEqual(m.convert(-99999), (-32768, True))
        r = InputRuntime(scale=m)
        r.push(1024, sequence=0)
        with self.assertRaises(ValueError):
            r.push(1024, sequence=2)
        self.assertEqual(r.index, 0)
        r.reset()
        self.assertEqual(r.index, -1)


if __name__ == '__main__':
    unittest.main()
