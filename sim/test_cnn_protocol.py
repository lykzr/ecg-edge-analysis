"""CNN四分类协议的身份/概率/边界拒绝测试，不操作设备。"""
import sys,struct,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/pc'))
from ecg_cnn import parse_result,parse_performance,Channel
def row(status=0,cls=0,p=(.7,.1,.1,.1),position=500,ready=800):
    return f'R,7,1,{position},{ready},{status},{cls},'+','.join(struct.pack('>f',v).hex() for v in p)
class ProtocolTests(unittest.TestCase):
    def test_four_classes(self):
        for i,label in enumerate(('N','S','V','F')):
            p=[.1]*4;p[i]=.7;self.assertEqual(parse_result(row(cls=i,p=p),7,1500,[])['label'],label)
    def test_unknown(self):self.assertEqual(parse_result(row(2,-1,(float('nan'),)*4),7,1500,[])['probability'],[None]*4)
    def test_reject_invalid(self):
        for value in (row(p=(1,1,1,1)),row(p=(float('nan'),.1,.1,.1)),row(cls=2),row(status=4),row(ready=1500),row(position=900),row().replace('R,7','R,8'),row().replace('R,7,1','R,7,2')):
            with self.assertRaises(ValueError):parse_result(value,7,1500,[])
    def test_hgb_is_not_cnn(self):
        class Port:
            def read(self):return b'H,HGB-PL-1,READY,500,mV,wrong\n'
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as d:
            ch=Channel(Port(),d)
            try:
                with self.assertRaises(ValueError):ch.wait_ready()
            finally:ch.close()
    def test_timing_scope(self):
        r=parse_performance('P,7,FP32,12,0,84000,42000,40000,333333333,100000000',7)
        self.assertEqual(r['scope'],'full_cnn_network');self.assertEqual(r['call_speedup'],2)
        for v in ('P,7,Q40,12,0,1,1,1,333333333,100000000','P,7,FP32,12,1,1,1,1,333333333,100000000','P,7,FP32,12,0,1,0,1,333333333,100000000'):
            with self.assertRaises(ValueError):parse_performance(v,7)
if __name__=='__main__':unittest.main()
