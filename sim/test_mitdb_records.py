"""多记录入口的导联选择、完整性拒绝和计分检查。"""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data'))
from ecg_dataset import BEAT_CODES, load_record, metrics


class MultiRecordChecks(unittest.TestCase):
    def test_reverse_lead_and_integrity(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as directory:
            raw = Path(directory)
            (raw/'999.hea').write_text('999 2 360 2\n999.dat 212 200 12 0 -2048 -1 0 V5\n999.dat 212 200(0)/mV 12 0 -1 -1 0 MLII\n')
            (raw/'999.dat').write_bytes(bytes([0,248,255,255,7,0]))
            (raw/'999.atr').write_bytes((1025).to_bytes(2,'little')+b'\0\0')
            def checksums():
                (raw/'SHA256SUMS.txt').write_text('\n'.join(
                    f'{hashlib.sha256((raw/name).read_bytes()).hexdigest()}  {name}'
                    for name in ('999.hea','999.dat','999.atr')))
            checksums()
            values,labels,meta = load_record(raw,'999','MLII')
            self.assertEqual(values,[-20,0])
            self.assertEqual(labels,[(1,1)])
            self.assertEqual(meta['adc_per_mv'],200)
            with self.assertRaises(ValueError):
                load_record(raw,'999','missing')
            (raw/'999.dat').write_bytes(b'\0'*6)
            with self.assertRaises(ValueError):
                load_record(raw,'999','MLII')
            checksums()
            with self.assertRaises(ValueError):
                load_record(raw,'999','MLII')

    def test_metrics_and_annotation_types(self):
        m,pairs,missed,extra = metrics([100,460,820],[102,461,1100],54)
        self.assertEqual((m['TP'],m['FN'],m['FP']),(2,1,1))
        self.assertAlmostEqual(m['position_mae_ms'],1.5*1000/360)
        self.assertAlmostEqual(m['rr_mae_ms'],1000/360)
        self.assertEqual(m['matched_rr_intervals'],1)
        self.assertTrue({1,5,8,12,38}.issubset(BEAT_CODES))
        self.assertTrue({14,16,24,28,31,37}.isdisjoint(BEAT_CODES))
        self.assertIsNone(metrics([100],[],54)[0]['rr_mae_ms'])


if __name__ == '__main__':
    unittest.main()
