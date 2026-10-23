"""历史清单路径兼容性与目录边界检查；不改训练基线内容。"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import unittest

from check_checkout import manifest_path, check, ROOT


class CheckoutTests(unittest.TestCase):
    def test_windows_and_posix_separators_resolve_same_file(self):
        base = ROOT/'model/baseline'
        expected = (base/'residual_verified/oof_metrics.json').resolve()
        for name in ('residual_verified/oof_metrics.json',
                     'residual_verified\\oof_metrics.json',
                     'residual_verified\\\\oof_metrics.json'):
            self.assertEqual(manifest_path(base, name), expected)
            # POSIX规则下转换后必须拆成目录和文件，而非含反斜杠的单一文件名。
            self.assertEqual(PurePosixPath(name.replace('\\', '/')).parts,
                             ('residual_verified', 'oof_metrics.json'))

    def test_absolute_drive_and_escape_paths_rejected(self):
        base = ROOT/'model/baseline'
        for name in ('/etc/passwd', 'C:\\file', 'C:file', '\\outside',
                     '//server/share/file', '../outside', '..\\outside', '', '.', None, 'bad\x00name'):
            with self.subTest(name=name), self.assertRaises((ValueError, TypeError)):
                manifest_path(base, name)

    def test_frozen_files_and_manifest_bytes_are_unchanged(self):
        path = ROOT/'model/baseline/files.json'; original = path.read_bytes()
        baseline = json.loads(original)
        for name, row in baseline['files'].items():
            data = manifest_path(ROOT/'model/baseline', name).read_bytes()
            self.assertEqual(len(data), row['bytes']); self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
        self.assertEqual(path.read_bytes(), original)

    def test_current_checkout(self):
        result = check()
        self.assertTrue(result['passed']); self.assertEqual(result['baseline_files'], 29)


if __name__ == '__main__': unittest.main()
