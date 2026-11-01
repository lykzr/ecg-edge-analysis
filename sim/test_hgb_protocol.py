"""HGB独立结果协议拒绝测试，不操作串口或板卡。"""
import sys,unittest,struct,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/pc'))
from ecg_hgb import parse_result,Channel,LEGACY_READY
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
    def test_startup_garbage_saved_only_before_ready(self):
        class Port:
            data=b'\xad\x7b\x67'+(LEGACY_READY+'\nA,7,READY,32\n').encode()
            def read(self):data=self.data;self.data=b'';return data
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            channel=Channel(Port(),directory)
            try:
                channel.wait_ready();self.assertEqual(channel.line(),'A,7,READY,32')
                self.assertEqual((Path(directory)/'startup_discard.bin').read_bytes(),b'\xad\x7b\x67')
                channel.buffer=bytearray(b'\xadBROKEN\n')
                with self.assertRaises(UnicodeDecodeError):channel.line()
            finally:channel.close()
    def test_wrong_ready_rejected(self):
        class Port:
            def read(self):return b'H,HGB-BATCH-1,READY,500,mV,WRONG_MODEL\n'
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            channel=Channel(Port(),directory)
            try:
                with self.assertRaisesRegex(ValueError,'身份'):channel.wait_ready()
            finally:channel.close()
    def test_startup_bound(self):
        class Port:
            def read(self):return b'bad'*3000
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            channel=Channel(Port(),directory)
            try:
                with self.assertRaisesRegex(ValueError,'8192'):channel.wait_ready()
            finally:channel.close()
if __name__=='__main__':unittest.main()
