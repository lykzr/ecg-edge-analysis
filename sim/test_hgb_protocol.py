"""HGB独立结果协议拒绝测试，不操作串口或板卡。"""
import sys,unittest,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/pc'))
from ecg_hgb import parse_result
def row(status=0,cls=0,probs=(.8,.1,.1),beat=1,pos=500,decision=1000):
    return f'R,7,{beat},{pos},800,{decision},{status},{cls},'+','.join(struct.pack('>d',v).hex() for v in probs)
class ResultTests(unittest.TestCase):
    def test_valid(self):self.assertEqual(parse_result(row(),7,1500,[])['label'],'N')
    def test_merged_vf(self):self.assertEqual(parse_result(row(cls=2,probs=(.1,.1,.8)),7,1500,[])['label'],'VF')
    def test_unknown(self):self.assertEqual(parse_result(row(2,-1,(float('nan'),)*3),7,1500,[])['probability'],[None]*3)
    def test_probabilities(self):
        for values in ((1.,1.,1.),(float('nan'),.1,.1),(-.1,.5,.6)):
            with self.assertRaises(ValueError):parse_result(row(probs=values),7,1500,[])
    def test_wrong_class(self):
        with self.assertRaises(ValueError):parse_result(row(cls=1),7,1500,[])
    def test_session(self):
        with self.assertRaises(ValueError):parse_result(row(),8,1500,[])
    def test_sequence(self):
        with self.assertRaises(ValueError):parse_result(row(beat=2),7,1500,[])
    def test_time(self):
        with self.assertRaises(ValueError):parse_result(row(decision=1500),7,1500,[])
    def test_unknown_not_normal(self):
        with self.assertRaises(ValueError):parse_result(row(status=4),7,1500,[])
if __name__=='__main__':unittest.main()
