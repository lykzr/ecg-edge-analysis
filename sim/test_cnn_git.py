"""Git数据入口的隔离、冻结文件校验和张量指纹检查，不下载/训练。"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data'));sys.path.insert(0, str(ROOT / 'model/prepare'))
from prepare_cnn_git import validate_protocol, array_digest


class GitInputTests(unittest.TestCase):
    def setUp(self):
        self.p = json.loads((ROOT / 'model/protocols/cnn_git_v1_protocol.json').read_text(encoding='utf-8'))

    def test_roles_and_download_set_exclude_independent_patients(self):
        validate_protocol(self.p)
        self.assertEqual(len(self.p['auxiliary_records']), 42)
        self.assertEqual(len(self.p['raw_sha256']), 3 * (61 + 42))
        self.assertEqual(self.p['candidates'], [{'id': 'residual_verified', 'family': 'residual', 'sources': 'verified'}])
        for role in ('development_records', 'auxiliary_records'):
            for row in self.p[role]:
                for ext in ('dat', 'hea', 'atr'):
                    self.assertIn(row['database'] + '/' + row['record'] + '.' + ext, self.p['raw_sha256'])

    def test_reject_test_patient_and_duplicate_folds(self):
        p = copy.deepcopy(self.p)
        p['development_records'][0]['subject'] = p['excluded_independent_test_subjects'][0]
        with self.assertRaises(ValueError):
            validate_protocol(p)
        p = copy.deepcopy(self.p); p['folds'][0].append(p['folds'][1][0])
        with self.assertRaises(ValueError):
            validate_protocol(p)

    def test_fingerprint_ignores_string_storage_width_but_detects_values(self):
        self.assertEqual(array_digest(np.array(['mit:100'], dtype='U7')),
                         array_digest(np.array(['mit:100'], dtype='U50')))
        self.assertNotEqual(array_digest(np.array(['mit:100'])), array_digest(np.array(['mit:101'])))
        a = np.array([1, 2], dtype=np.float32)
        self.assertNotEqual(array_digest(a), array_digest(a[::-1]))


if __name__ == '__main__':
    unittest.main()
