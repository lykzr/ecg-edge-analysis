"""噪声计分的边界、分段分母和V召回检查；不运行检测器。"""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'data'))
from evaluate_qrs_noise import score, region, decode_channels
GATE=dict(sensitivity=.99,positive_predictivity=.99,position_mae_ms=10,rr_mae_ms=15,v_recall=.99)


class NoiseScoring(unittest.TestCase):
    def test_decode16_signed_interleaved(self):
        import struct
        blob=struct.pack('<hhhh',-32768,32767,-1,0)
        self.assertEqual(decode_channels(blob,'16',2),[[-32768,-1],[32767,0]])
        with self.assertRaises(ValueError):decode_channels(blob[:-1],'16',2)

    def test_decode212_length(self):
        self.assertEqual(decode_channels(bytes(3),'212',1),[[0],[0]])
        with self.assertRaises(ValueError):decode_channels(bytes(3),'212',2)
    def test_full_start_tail_and_v(self):
        m,*_=score([(0,1),(100,5),(649999,5)],[0,100],650000,54,GATE)
        self.assertEqual((m['TP'],m['FN'],m['FP']),(2,1,0))
        self.assertEqual(m['v_recall'],.5)
        self.assertEqual(m['provisional_gate'],'FAIL')

    def test_region_boundaries(self):
        self.assertEqual(region(107999),'startup_clean')
        self.assertEqual(region(108000),'noise_on')
        self.assertEqual(region(151199),'noise_on')
        self.assertEqual(region(151200),'noise_off')

    def test_boundary_match_once(self):
        m,*_=score([(107999,5),(151199,1)],[108001,151201,160000],200000,54,GATE)
        self.assertEqual((m['TP'],m['FN'],m['FP']),(2,0,1))
        self.assertEqual(sum(b['TP'] for b in m['time_blocks']),2)
        self.assertEqual(sum(b['FP'] for b in m['time_blocks']),1)
        self.assertEqual(sum(b['v_reference'] for b in m['time_blocks']),1)

    def test_no_duplicate_or_float(self):
        for positions in ([100,100],[100.0],[-1],[1000]):
            with self.assertRaises(ValueError):score([(100,1)],positions,1000,54,GATE)

    def test_no_v_is_unknown(self):
        m,*_=score([(100,1)],[100],1000,54,GATE)
        self.assertIsNone(m['v_recall'])
        self.assertTrue(m['checks']['v_recall'])

    def test_empty_detection(self):
        m,*_=score([(100,5)],[],1000,54,GATE)
        self.assertEqual(m['FN'],1)
        self.assertEqual(m['v_recall'],0)
        self.assertIsNone(m['positive_predictivity'])

if __name__=='__main__':unittest.main()
