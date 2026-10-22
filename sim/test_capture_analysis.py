"""输入诊断的能量、常量平移及保护边界回归，不评价无标注心电准确率。"""
import csv
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capture_analysis', ROOT/'data/analyze_capture.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class AnalysisChecks(unittest.TestCase):
    def test_energy_threshold_dead_zone(self):
        cfg = analysis.Config(sample_rate_hz=500)
        result = analysis.diagnose([2100 + (i % 20) for i in range(2000)], cfg)
        self.assertEqual(result['event_count'], 0)
        self.assertLess(result['energy_max'], 4096)
        self.assertGreaterEqual(result['threshold_min'], 4096)
        self.assertTrue(result['independent_energy_equal'])

    def test_translation_does_not_fix_derivative_scale(self):
        values = [1000 + (i % 30)*3 for i in range(2000)]
        cfg = analysis.Config(sample_rate_hz=500)
        first = analysis.diagnose(values, cfg)
        second = analysis.diagnose([v-1000 for v in values], cfg)
        for key in ('energy_max', 'threshold_min', 'events'):
            self.assertEqual(first[key], second[key])

    def test_real_event_path_and_full_trace(self):
        values = [0]*100 + [20000] + [0]*500
        stream = io.StringIO()
        result = analysis.diagnose(values, analysis.Config(sample_rate_hz=500), csv.writer(stream))
        self.assertEqual(result['events'][0], dict(index=70, rr=0))
        self.assertEqual(len(stream.getvalue().splitlines()), len(values))

    def test_empty_or_overflow_rejected(self):
        with self.assertRaises(ValueError):
            analysis.diagnose([], analysis.Config())
        with self.assertRaises(ValueError):
            analysis.diagnose([32768], analysis.Config())

    def test_vendor_csv_provenance_and_no_overwrite(self):
        base = ROOT/'tmp/capture_analysis_tests'
        base.mkdir(parents=True, exist_ok=True)
        # 保留测试输出，避免跨环境临时目录自动清理权限差异。
        directory = Path(tempfile.mkdtemp(dir=base))
        source = directory/'source.csv'
        source.write_text('timestamp(s),resp_raw,ecg_raw,resp_filtered,ecg_filtered\n'+
                          ''.join(f'{i/500},8388608,{8388608+2100*256},0,0\n' for i in range(200)),encoding='utf-8')
        result = analysis.analyze(source,directory/'output')
        self.assertEqual(result['source_samples'],200)
        self.assertEqual(result['cases']['raw_shift8']['energy_max'],0)
        self.assertIsNone(result['clinical_or_detection_accuracy'])
        with self.assertRaises(FileExistsError):
            analysis.analyze(source,directory/'output')


if __name__ == '__main__':
    unittest.main()
