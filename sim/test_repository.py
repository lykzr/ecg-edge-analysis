"""核对仓库检查能拒绝漏跟踪、本地历史混入和失效链接。"""
from pathlib import Path
import tempfile
import unittest
from check_repository import inspect

class RepositoryTests(unittest.TestCase):
    def test_required_untracked_and_ignored_files_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'a.py').write_text('pass', encoding='utf-8')
            report = inspect(root, ['a.py'], ['b.py'], ['a.py'])
            self.assertFalse(report['passed'])
            self.assertEqual(len(report['errors']), 2)

    def test_links_must_resolve_to_tracked_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'README.md').write_text('[说明](note.md)', encoding='utf-8')
            (root / 'note.md').write_text('正文', encoding='utf-8')
            self.assertFalse(inspect(root, ['README.md'], [], [])['passed'])
            self.assertTrue(inspect(root, ['README.md', 'note.md'], [], [])['passed'])
            (root / 'note.md').unlink()
            self.assertFalse(inspect(root, ['README.md', 'note.md'], [], [])['passed'])

    def test_personal_settings_must_not_be_tracked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'myself.md').write_text('个人配置', encoding='utf-8')
            self.assertFalse(inspect(root, ['myself.md'], [], [])['passed'])

if __name__ == '__main__':
    unittest.main()
