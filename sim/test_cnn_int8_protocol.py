"""量化协议必须区分固件身份、同精度错误及跨精度类别变化。"""
import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_cnn import parse_performance,parse_quant_performance,transfer,STREAM_READY
from ecg_cnn_stream import transfer_stream
from test_cnn_stream_protocol import Port
from ecg_cnn import TRIPLE_READY

class QuantProtocolTests(unittest.TestCase):
    def test_comparison_scope_and_validation(self):
        p=parse_performance('P,7,W8A8,2,0,400,100,90,1000000,100000000',7,'W8A8')
        q=parse_quant_performance('Q,7,2,1,600,200,400,100,1000000',7,p)
        self.assertEqual(q['class_changes'],1)
        self.assertEqual(q['quantization_pl_speedup'],2)
        for s in ('Q,8,2,1,600,200,400,100,1000000','Q,7,2,3,600,200,400,100,1000000','Q,7,2,1,600,200,400,101,1000000','Q,7,2,1,600,200,400,100,0'):
            with self.assertRaises(ValueError):parse_quant_performance(s,7,p)
        with self.assertRaises(ValueError):parse_performance('P,7,W8A8,2,0,400,100,90,1000000,100000000',7)

    def test_old_firmware_rejected_before_send(self):
        class Old:
            def __init__(self):self.writes=[]
            def read(self):return (STREAM_READY+'\n').encode()
            def write(self,v):self.writes.append(v)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            port=Old()
            with self.assertRaises(ValueError):transfer([0.]*32,port,d,'hp05',7,precision='W8A8')
            self.assertEqual(port.writes,[])

    def test_int8_stream_updates_comparison(self):
        class QuantPort(Port):
            def __init__(self):
                super().__init__(lambda s:s.replace('P,7,FP32','P,7,W8A8').replace('A,7,NEXT,64','Q,7,1,0,600,300,200,100,1000000\nA,7,NEXT,64'))
                self.buffer=(TRIPLE_READY+'\n').encode()
            def write(self,data):
                if data.startswith(b'D,'):
                    self.buffer+=b'P,7,W8A8,1,0,200,100,90,1000000,100000000\nQ,7,1,0,600,300,200,100,1000000\nD,7,64,1,0,2,3,4\n'
                    return len(data)
                return super().write(data)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            seen=[];p=QuantPort()
            r=transfer_stream([[0.]*32]*2,p,d,'hp05',64,sid=7,precision='W8A8',on_update=lambda r:seen.append(r['quantization_comparison']))
            self.assertEqual(r['precision'],'W8A8')
            self.assertEqual(r['quantization_comparison']['quantization_pl_speedup'],3)
            self.assertTrue(any(s is not None for s in seen))
            self.assertTrue(p.writes[0].startswith(b'I,CNN-INT8-STREAM-1,'))

    def test_int8_batch_accepts_performance_before_rows(self):
        import struct
        class BatchPort:
            def __init__(self):self.buffer=(TRIPLE_READY+'\n').encode();self.writes=[]
            def read(self):v=self.buffer;self.buffer=b'';return v
            def write(self,data):
                self.writes.append(data)
                if data.startswith(b'I,'):self.buffer+=b'A,7,READY,32\n'
                elif data.startswith(b'B,'):self.end=int(data.split(b',')[2])+int(data.split(b',')[3])
                elif data.startswith(b'D,'):
                    probs=','.join(struct.pack('>f',v).hex() for v in (.7,.1,.1,.1))
                    self.buffer+=('P,7,W8A8,1,0,200,100,90,1000000,100000000\nQ,7,1,0,600,300,200,100,1000000\nR,7,1,10,63,0,0,'+probs+'\nD,7,64,1,0,2,3,4\n').encode()
                else:self.buffer+=f'A,7,NEXT,{self.end}\n'.encode()
                return len(data)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as d:
            p=BatchPort();r=transfer([0.]*64,p,d,'hp05',7,precision='W8A8')
            self.assertTrue(r['passed']);self.assertEqual(r['quantization_comparison']['beats'],1)
            self.assertEqual(r['events'][0]['label'],'N')

if __name__=='__main__':unittest.main()
