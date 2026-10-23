"""模型迁移的旧路径解析与冻结基线核验；不训练或读取独立测试。"""
from pathlib import Path
import unittest
from check_baseline import source_path, check, ROOT


class ModelPathTests(unittest.TestCase):
    def test_old_protocol_and_training_paths_portable(self):
        for old, new in [('data/cnn_git_v1_protocol.json', 'model/protocols/cnn_git_v1_protocol.json'),
                         ('data/train_cnn_cv.py', 'model/baseline/legacy_sources/train_cnn_cv.py'),
                         ('data/prepare_cnn_git.py', 'model/prepare/prepare_cnn_git.py'),
                         ('data/baseline/protocol.json', 'model/baseline/protocol.json')]:
            for name in (old, old.replace('/', '\\')):
                self.assertEqual(source_path(name).resolve(), (ROOT / new).resolve())
                self.assertTrue(source_path(name).is_file())

    def test_escape_rejected(self):
        for name in ('../x', '/etc/passwd', 'C:/x', 'C:x', '\\outside', ''):
            with self.assertRaises((ValueError, TypeError)):
                source_path(name)

    def test_baseline_byte_integrity(self):
        result = check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['file_count'], 29)
        self.assertFalse(result['model_accepted'])
        self.assertFalse(result['weights_replayed'])


if __name__ == '__main__':
    unittest.main()
