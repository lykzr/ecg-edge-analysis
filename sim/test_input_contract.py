"""合同与当前实际C接收器核对，不接真实ECG。"""
import unittest
import test_runtime_link as t
from ecg_bridge_protocol import encode
class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):t.LinkTests.setUpClass();cls.lib=t.LinkTests.lib
    def test_runtime_rejects_500_unknown_scale_and_adc(self):
        for rate,source,scale in [('500','REPLAY','4096'),('360','REPLAY','-1'),('360','ADC','4096')]:
            node=t.Node(self.lib)
            for b in encode(f'I,ECG-IN-1,c,{rate},{source},{scale}'):self.lib.ecg_link_feed(node.state,b,node.now)
            for _ in range(50):node.tick()
            data=bytes(node.rx);self.assertIn(b',ERROR,',data);self.assertNotIn(b',READY,',data)
    def test_gap_does_not_accept_or_echo(self):
        node=t.Node(self.lib)
        for b in encode('I,ECG-IN-1,c,360,REPLAY,4096'):self.lib.ecg_link_feed(node.state,b,node.now)
        for _ in range(20):node.tick()
        node.rx.clear()
        for b in encode('D,1,1,0'):self.lib.ecg_link_feed(node.state,b,node.now)
        for _ in range(20):node.tick()
        data=bytes(node.rx);self.assertIn(b',ERROR,',data);self.assertFalse(any(x.startswith(b'W,') for x in data.splitlines()))
if __name__=='__main__':unittest.main()
