"""准备算子的独立手算与边界，不代替RTL仿真。"""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/reference'))
from ecg_int8_ops import conv1d_valid,maxpool1d,requantize
class IntegerTests(unittest.TestCase):
    def test_round_signed_ties_and_saturation(self):
        self.assertEqual([requantize(x,1) for x in [1,-1,3,-3,255,-257]],[1,-1,2,-2,127,-128])
        self.assertEqual(requantize(-2147483648,31),-1)
        self.assertEqual(requantize(-1,0,True),0)
    def test_multichannel_hand_computation(self):
        self.assertEqual(conv1d_valid([[1,2,3],[4,5,6]],[[[1,-1],[2,1]]],[3],0),[[15,18]])
    def test_signed_pool_and_tail(self):
        self.assertEqual(maxpool1d([[-128,-1,-5,-6,127]],2),[[-1,-5]])
    def test_bounds_reject(self):
        for a,s in [(1<<31,0),(0,32),(0,-1)]:
            with self.assertRaises(ValueError):requantize(a,s)
        with self.assertRaises(ValueError):conv1d_valid([[128]],[[[1]]],[0],0)
        with self.assertRaises(ValueError):conv1d_valid([[1]],[[[1]]],[2147483647],0)
        with self.assertRaises(ValueError):conv1d_valid([[1],[1,2]],[[[1],[1]]],[0],0)
if __name__=='__main__':unittest.main()
