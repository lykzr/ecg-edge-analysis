"""可选PyTorch环境的卷积数值、训练更新与评估隔离检查。"""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

HAS_TORCH=importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    ROOT=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(ROOT/'src/reference'));sys.path.insert(0,str(ROOT/'data'));sys.path.insert(0,str(ROOT/'model/train'))
    from ecg_trainable_cnn import create_model,waveform_channels,budget
    from train_cnn_candidates import gate
    from train_cnn_refined import augment,construct


@unittest.skipUnless(HAS_TORCH,'需在独立PyTorch环境运行')
class TorchCnnChecks(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2);torch.manual_seed(53)

    def test_all_architectures_update_convolutions(self):
        for family in ('mf','residual'):
            for feature in ('raw','derivative','both'):
                model=create_model({'family':family,'feature':feature,'width':12 if family=='mf' else 16})
                conv=next(m for m in model.modules() if isinstance(m,torch.nn.Conv1d))
                before=conv.weight.detach().clone()
                x=torch.randn(8,64);rr=torch.rand(8,3);y=torch.arange(8)%4
                opt=torch.optim.Adam(model.parameters(),lr=.01)
                loss=torch.nn.functional.cross_entropy(model(x,rr),y)
                loss.backward()
                self.assertTrue(torch.isfinite(conv.weight.grad).all())
                self.assertGreater(float(conv.weight.grad.abs().sum()),0)
                opt.step();self.assertFalse(torch.equal(before,conv.weight))

    def test_eval_independent_of_batch_companions(self):
        for family in ('mf','residual'):
            model=create_model({'family':family,'feature':'both','width':12 if family=='mf' else 16}).eval()
            x=torch.randn(7,64);rr=torch.rand(7,3)
            with torch.no_grad():
                a=model(x,rr);b=torch.cat([model(x[i:i+1],rr[i:i+1]) for i in range(7)])
            torch.testing.assert_close(a,b,rtol=1e-5,atol=1e-6)

    def test_same_padding_matches_scalar_correlation(self):
        model=create_model({'family':'mf','feature':'raw','width':12})
        x=torch.randn(2,64)
        conv=model.wave[1]
        with torch.no_grad():
            actual=model.wave[:2](x[:,None,:]).numpy()
        padded=np.pad(x.numpy(),((0,0),(15,16)))
        kernel=conv.weight.detach().numpy()[:,0,:];bias=conv.bias.detach().numpy()
        expected=np.array([[[sum(padded[b,t+i]*kernel[f,i] for i in range(32))+bias[f] for t in range(64)] for f in range(12)] for b in range(2)])
        np.testing.assert_allclose(actual,expected,atol=2e-6,rtol=1e-5)

    def test_no_false_gate_pass_for_collapsed_class(self):
        limits={'macro_f1':.85,'minimum_class_f1':.7,'recall':[.95,.8,.8,.7],'maximum_parameters':100000}
        result=gate({'macro_f1':.9,'f1':[.99,.99,.99,0],'recall':[.99,.99,.99,0]}, {'trainable_parameters':1000},limits)
        self.assertFalse(result['passed']);self.assertIn('F_f1',result['failed_checks'])
        self.assertIn('F_recall',result['failed_checks'])

    def test_derivative_and_budget_have_no_hidden_batch_factor(self):
        x=torch.tensor([[1.,2.,4.,8.]])
        torch.testing.assert_close(waveform_channels(x,'derivative'),torch.tensor([[[0.,1.,2.,4.]]]))
        model=create_model({'family':'mf','feature':'raw','width':12})
        result=budget(model)
        self.assertEqual(result['trainable_parameters'],sum(p.numel() for p in model.parameters()))
        self.assertLess(result['trainable_parameters'],100000)

    def test_augmentation_is_seeded_finite_and_does_not_mutate_input(self):
        x=torch.randn(8,64);before=x.clone()
        torch.manual_seed(82);a=augment(x)
        torch.manual_seed(82);b=augment(x)
        torch.testing.assert_close(a,b,rtol=0,atol=0)
        torch.testing.assert_close(x,before,rtol=0,atol=0)
        self.assertTrue(torch.isfinite(a).all())
        self.assertFalse(torch.equal(a,x))

    def test_no_bn_variant_has_no_running_statistics(self):
        model=construct({'family':'residual','feature':'both','width':16,'batch_norm':'none'})
        self.assertFalse(any(isinstance(m,torch.nn.BatchNorm1d) for m in model.modules()))
        self.assertEqual(model(torch.randn(3,64),torch.randn(3,3)).shape,(3,4))

    def test_context128_model_and_mac_accounting(self):
        for family in ('mf','residual'):
            config={'family':family,'feature':'both','width':12 if family=='mf' else 16,'input_samples':128}
            model=create_model(config)
            self.assertEqual(model(torch.randn(3,128),torch.randn(3,3)).shape,(3,4))
            long_budget=budget(model)
            config['input_samples']=64
            short_budget=budget(create_model(config))
            self.assertGreater(long_budget['conv_linear_macs_per_beat'],short_budget['conv_linear_macs_per_beat'])


if __name__=='__main__':
    unittest.main()
