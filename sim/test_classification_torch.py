"""既有失败开发权重接口重放；不训练、不读独立测试或用输出选型。"""
from pathlib import Path
import sys
import unittest
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/reference'),str(ROOT/'model/train')]
from ecg_classifier import TorchBackend, Request, normalize_rr
from train_cnn_cv import tensors


class TorchInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend=TorchBackend(0)

    def test_fold_rr_normalization_matches_training_function(self):
        b=self.backend
        basic=np.asarray([[.25,.25,.25],[0.,1.,.125]],dtype=np.float32)
        arrays=dict(x=np.zeros((2,128),dtype=np.float32),rr=basic,y=np.zeros(2,dtype=np.int64))
        expected,_=tensors(arrays,dict(rr_mean=list(b.spec.rr_mean),rr_std=list(b.spec.rr_std)))
        for n,row in enumerate(basic):
            np.testing.assert_array_equal(normalize_rr(row,b.spec),expected[1][n].numpy())

    def test_actual_weight_wrapper_matches_direct_inference(self):
        b=self.backend;s=b.spec
        x=tuple(float(v) for v in np.linspace(-1,1,128,dtype=np.float32))
        rr=tuple(float(v) for v in normalize_rr([.25,.25,.25],s))
        r=Request('unit',1,360,360,360,600,s.model_id,s.weights_sha256,s.preprocess_sha256,x,rr)
        result=b.infer(r)
        with torch.no_grad():
            direct=b.model(torch.tensor([x]),torch.tensor([rr])).argmax(1).item()
        self.assertEqual(result.class_id,direct)
        self.assertTrue(result.valid)
        self.assertFalse(result.accepted)

    def test_first_rr_does_not_run_as_normal(self):
        b=self.backend;s=b.spec
        r=Request('unit',1,360,0,360,600,s.model_id,s.weights_sha256,s.preprocess_sha256,(0.,)*128,(),'MISSING_RR')
        self.assertFalse(b.infer(r).valid)


if __name__=='__main__':unittest.main()
