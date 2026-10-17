"""长程辅助数据：限定历史RR、先选训练样本以及未知幅值的处理。"""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'data'))
HAS_DATA=importlib.util.find_spec('wfdb') is not None
if HAS_DATA:
    import numpy as np
    from extend_cnn_ltdb import selected_beats
    from prepare_cnn_expanded import causal_rr,common_window


@unittest.skipUnless(HAS_DATA,'需要WFDB/SciPy数据环境')
class LongTermTests(unittest.TestCase):
    def test_bounded_history_matches_full_causal_history(self):
        rng=np.random.default_rng(6);history=rng.uniform(.4,1.2,10000).tolist()
        np.testing.assert_array_equal(causal_rr(history),causal_rr(history[-401:]))

    def test_selection_keeps_all_beats_in_rr_even_if_capped_or_unknown(self):
        p={'window':{'before_seconds':.2,'after_seconds':.3},'train_sampling':{'seed':1},
           'ltdb':{'caps_per_record_class':[1,1,1,1]}}
        ann=SimpleNamespace(sample=np.array([100,200,250,400,500]),symbol=['N','Q','F','N','F'])
        rows,excluded,counts=selected_beats(ann,1000,100,p,'synthetic')
        self.assertEqual(counts[3],2);self.assertEqual(sum(r[1]==3 for r in rows),1)
        self.assertEqual(excluded['unmapped_Q'],1)
        for index,cls,symbol,rr in rows:
            history=[1.,.5] if index==250 else ([1.,.5,1.5] if index==400 else [1.,.5,1.5,1.])
            np.testing.assert_allclose(rr,causal_rr(history))

    def test_adc_zscore_does_not_invent_millivolts(self):
        cfg={'before_seconds':128/360,'after_seconds':192/360,'target_hz':144,'output_samples':128,'std_floor_mv':1.0}
        signal=np.sin(np.arange(500)/5)*100
        np.testing.assert_allclose(common_window(signal,200,128,cfg),common_window(signal*3,200,128,cfg),atol=2e-7)


if __name__=='__main__':
    unittest.main()
