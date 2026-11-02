"""流式契约：运行中回调、逐拍/累计计时、提前结束与输入身份拒绝。"""
import json,struct,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_cnn import STREAM_READY
from ecg_cnn_stream import transfer_stream,MODEL_READY

class Port:
    def __init__(self,mutate=lambda s:s):self.buffer=(STREAM_READY+'\n').encode();self.writes=[];self.mutate=mutate
    def read(self):out=self.buffer;self.buffer=b'';return out
    def write(self,data):
        self.writes.append(data)
        if data.startswith(b'I,'):self.buffer+=(MODEL_READY+'\nA,7,READY,32\n').encode()
        elif data.startswith(b'B,'):self.end=int(data.split(b',')[2])+int(data.split(b',')[3])
        elif len(data)==256 and self.end==32:
            self.buffer+=b'A,7,NEXT,32\n'
        elif len(data)==256 and self.end==64:
            p=','.join(struct.pack('>f',v).hex() for v in (.7,.1,.1,.1))
            self.buffer+=self.mutate('T,7,1,63,200,100,90,20,0,0\nR,7,1,10,63,0,0,'+p+'\nP,7,FP32,1,0,200,100,90,1000000,100000000\nA,7,NEXT,64\n').encode()
        elif data.startswith(b'D,'):self.buffer+=b'P,7,FP32,1,0,200,100,90,1000000,100000000\nD,7,64,1,0,2,3,4\n'
        return len(data)

class StreamTests(unittest.TestCase):
    def test_cumulative_speedup_updates_for_each_beat(self):
        class TwoBeats(Port):
            def write(self,data):
                if len(data)==256 and self.end==96:
                    p=','.join(struct.pack('>f',v).hex() for v in (.7,.1,.1,.1))
                    self.buffer+=('T,7,2,95,300,100,90,20,0,0\nR,7,2,50,95,0,0,'+p+
                        '\nP,7,FP32,2,0,500,200,180,1000000,100000000\nA,7,NEXT,96\n').encode()
                    return len(data)
                if data.startswith(b'D,'):
                    self.buffer+=b'P,7,FP32,2,0,500,200,180,1000000,100000000\nD,7,96,2,0,2,3,4\n'
                    return len(data)
                return super().write(data)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            seen={}
            def update(r):
                if r['performance']:seen[r['performance']['beats']]=r['performance']['call_speedup']
            transfer_stream([[0.]*32]*3,TwoBeats(),d,'hp05',96,sid=7,on_update=update)
            self.assertEqual(seen,{1:2,2:2.5})

    def test_progress_and_sums(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            seen=[];r=transfer_stream([[0.]*32,[0.]*32],Port(),d,'hp05',64,sid=7,on_update=lambda r:seen.append((r['passed'],len(r['events']))))
            self.assertTrue(r['passed']);self.assertIn((False,1),seen)
            self.assertEqual(r['performance']['call_speedup'],2)
            self.assertEqual(r['events'][0]['algorithm_wait_ms'],106)
    def test_reject_corrupt_measurement(self):
        for change in (lambda s:s.replace('200,100,90,20,0,0','200,100,90,20,0,1'),
                       lambda s:s.replace('1,0,200,100,90,1000000','1,0,201,100,90,1000000'),
                       lambda s:s.replace('T,7,1,63','T,7,2,63'),
                       lambda s:'D,7,64,0,0,0,0,0\n'):
            with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
                with self.assertRaises(ValueError):transfer_stream([[0.]*32,[0.]*32],Port(change),d,'hp05',64,sid=7)
    def test_old_firmware_no_samples(self):
        port=Port();port.buffer=b'H,ECG-DUAL-1,READY,500,mV,H27-FP32,HGB-Q40\n'
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            with self.assertRaises(ValueError):transfer_stream([[0.]*32],port,d,'hp05',32,sid=7)
        self.assertFalse(any(v.startswith(b'B,') for v in port.writes))

if __name__=='__main__':unittest.main()
