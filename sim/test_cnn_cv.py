"""患者分折、来源消融与保留时间结构CNN的检查。"""
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np
from verify_cnn_cv import metrics

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'data'));sys.path.insert(0,str(ROOT/'src/reference'))
DATA=importlib.util.find_spec('wfdb') is not None
TORCH=importlib.util.find_spec('torch') is not None
if DATA:from prepare_cnn_cv import validate_folds
if TORCH:
    import torch
    from ecg_temporal_cnn import TemporalCnn
    from ecg_trainable_cnn import budget
    from train_cnn_cv import split_arrays


@unittest.skipUnless(DATA,'需要WFDB数据环境')
class FoldTests(unittest.TestCase):
    def test_patient_cannot_appear_twice_or_in_test(self):
        validate_folds([['a'],['b'],['c']],['d'])
        with self.assertRaises(ValueError):validate_folds([['a'],['a']],['d'])
        with self.assertRaises(ValueError):validate_folds([['a'],['b']],['b'])


@unittest.skipUnless(TORCH,'需要项目CPU PyTorch环境')
class CvTorchTests(unittest.TestCase):
    def test_temporal_model_updates_and_eval_batch_invariance(self):
        torch.set_num_threads(2);torch.manual_seed(12);model=TemporalCnn(16)
        x=torch.randn(8,128);rr=torch.randn(8,3);y=torch.arange(8)%4
        opt=torch.optim.AdamW(model.parameters(),lr=.001);before=model.wave[0].weight.detach().clone()
        loss=torch.nn.functional.cross_entropy(model(x,rr),y);loss.backward();opt.step()
        self.assertFalse(torch.equal(before,model.wave[0].weight));self.assertTrue(torch.isfinite(loss))
        model.eval()
        with torch.no_grad():torch.testing.assert_close(model(x[:1],rr[:1]),model(x,rr)[:1],atol=1e-6,rtol=1e-5)
        self.assertLess(budget(model)['trainable_parameters'],100000)

    def test_source_ablation_preserves_all_validation_and_patient_isolation(self):
        def arrays(subjects,records):
            return {'x':np.zeros((len(subjects)*4,128),np.float32),'rr':np.ones((len(subjects)*4,3),np.float32),
                    'y':np.tile(np.arange(4),len(subjects)), 'subject':np.repeat(subjects,4),
                    'record':np.repeat(records,4),'r_index':np.tile(np.arange(4),len(subjects))}
        dev=arrays(['incart:1','incart:2'],['incartdb:I01','incartdb:I03'])
        aux=arrays(['mit:1','svdb:identity_unknown_pool'],['mitdb:100','svdb:800'])
        p={'train_sampling':{'seed':7,'per_verified_subject_per_class':[1,1,1,1]},'excluded_independent_test_subjects':['incart:3']}
        train,val=split_arrays(dev,aux,['incart:2'],{'sources':'verified'},p)
        self.assertEqual(len(val['y']),4);self.assertEqual(set(val['subject']),{'incart:2'})
        self.assertEqual(set(train['subject']),{'incart:1','mit:1'})
        all_train,_=split_arrays(dev,aux,['incart:2'],{'sources':'all'},p)
        self.assertIn('svdb:identity_unknown_pool',set(all_train['subject']))
        bad=arrays(['incart:2'],['incartdb:I04'])
        with self.assertRaises(ValueError):split_arrays(dev,bad,['incart:2'],{'sources':'all'},p)


class IndependentMetricsTests(unittest.TestCase):
    def test_controlled_confusions_and_invalid_labels(self):
        result=metrics(np.array([0,0,1,2,3]),np.array([0,1,1,2,0]))
        self.assertEqual(result['confusion_matrix_rows_true'],[[1,1,0,0],[0,1,0,0],[0,0,1,0],[1,0,0,0]])
        np.testing.assert_allclose(result['f1'],[.5,2/3,1.,0.])
        self.assertAlmostEqual(result['macro_f1'],13/24)
        self.assertAlmostEqual(result['accuracy'],.6)
        with self.assertRaises(ValueError):metrics(np.array([4]),np.array([0]))


if __name__=='__main__':unittest.main()
