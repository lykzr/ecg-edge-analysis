"""扩库患者隔离和跨采样率切拍检查；不代替真实模型质量评估。"""
from pathlib import Path
import sys
import unittest
import json

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data'))

try:
    import numpy as np
    from prepare_cnn_expanded import common_window, validate_splits, causal_rr
    HAS_DATA=True
except ImportError:
    HAS_DATA=False


@unittest.skipUnless(HAS_DATA,'需要WFDB/SciPy数据环境')
class ExpandedTests(unittest.TestCase):
    def test_same_patient_different_records_cannot_cross_roles(self):
        a={'database':'incartdb','record':'I01','subject':'incart:1'}
        b=dict(a,record='I02')
        validate_splits({'train':[a,b],'validation':[],'test':[]})
        with self.assertRaises(ValueError):
            validate_splits({'train':[a],'validation':[],'test':[b]})

    def test_unknown_identity_source_not_holdout(self):
        r={'database':'svdb','record':'800','subject':'svdb:identity_unknown_pool'}
        with self.assertRaises(ValueError):
            validate_splits({'train':[],'validation':[r],'test':[]})

    def test_frozen_protocol_subject_support(self):
        p=json.loads((ROOT/'data/cnn_expanded_v6_protocol.json').read_text(encoding='utf-8'))
        validate_splits(p['splits'])
        for role in ('validation','test'):
            rows=p['splits'][role]
            self.assertEqual({r['database'] for r in rows},{'incartdb'})
            self.assertEqual(len({r['subject'] for r in rows}),6)
            for cls in ('S','F'):
                self.assertGreaterEqual(len({r['subject'] for r in rows if r['counts'][cls]>0}),3)

    def test_physical_time_alignment_across_sampling_rates(self):
        cfg={'before_seconds':128/360,'after_seconds':192/360,'target_hz':144,'output_samples':128,'std_floor_mv':.05}
        waves=[]
        for fs in (128,257,360):
            t=np.arange(3*fs)/fs-1
            wave=np.exp(-.5*(t/.024)**2)+.15*np.sin(2*np.pi*6*t)
            waves.append(common_window(wave,fs,fs,cfg))
        for w in waves:
            self.assertEqual(w.shape,(128,));self.assertTrue(np.isfinite(w).all())
            self.assertLess(abs(int(np.argmax(w))-51.2),1.5)
        # 零边界的滤波瞬态随原采样网格变化；主体与整体误差分别核对。
        error=waves[0]-waves[-1]
        self.assertLess(float(np.max(np.abs(error[5:-5]))),.04)
        self.assertLess(float(np.sqrt(np.mean(error**2))),.02)
        self.assertIsNone(common_window(np.zeros(100),1,128,cfg))

    def test_rr_uses_past_intervals(self):
        np.testing.assert_allclose(causal_rr([1.,.5]),[.125,.125,.25])
        np.testing.assert_allclose(causal_rr([.5]),[.25,.25,.25])

    def test_360hz_preserves_previous_context_representation(self):
        from scipy.signal import resample_poly
        cfg={'before_seconds':128/360,'after_seconds':192/360,'target_hz':144,'output_samples':128,'std_floor_mv':.05}
        signal=np.random.default_rng(7).normal(size=1000)
        expected=resample_poly(signal[360-128:360+192],2,5,padtype='constant')
        expected-=expected.mean();expected/=max(float(expected.std()),.05)
        np.testing.assert_allclose(common_window(signal,360,360,cfg),expected,atol=2e-7,rtol=2e-7)


if __name__=='__main__':
    unittest.main()
