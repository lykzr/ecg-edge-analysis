"""发布清单防错和复制后运行回归；不连接板卡，不把隐藏窗口当人工验收。"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from check_system_release import check, safe

ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'releases/latest'


class ReleaseChecks(unittest.TestCase):
    def test_relative_paths_reject_escape(self):
        for name in ('../outside','/absolute','C:/outside','x\\y','\x00',''):
            with self.assertRaises((ValueError,TypeError)):
                safe(ROOT,name)

    def test_current_candidate_sources_and_board_evidence(self):
        result=check(CANDIDATE,ROOT)
        self.assertTrue(result['passed'])
        self.assertEqual(result['cases']['paced']['samples'],60003)
        self.assertFalse(result['hardware_operated'])

    def test_tampered_image_rejected(self):
        root=ROOT/'tmp/system_release_tests';root.mkdir(parents=True,exist_ok=True)
        directory=Path(tempfile.mkdtemp(dir=root))/'copy'
        shutil.copytree(CANDIDATE,directory)
        path=directory/'bridge/prebuilt/ecg_bridge.elf'
        data=path.read_bytes();path.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaises((ValueError,AssertionError)):check(directory,ROOT)

    def test_portable_artifacts_use_repository_sources(self):
        root=ROOT/'tmp/system_release_tests';root.mkdir(parents=True,exist_ok=True)
        base=Path(tempfile.mkdtemp(dir=root));directory=base/'portable'
        shutil.copytree(CANDIDATE,directory)
        self.assertTrue(check(directory,ROOT)['passed'])
        self.assertFalse((directory/'src').exists())
        self.assertFalse((directory/'docs').exists())
        self.assertEqual(check(directory,ROOT)['files'],17)

    def test_scripts_resolve_package_local_hardware(self):
        for name in ('smoke','bridge'):
            script=(CANDIDATE/name/('run_'+name+'.tcl')).read_text()
            self.assertIn('[file dirname [info script]]',script)
            self.assertNotIn('[file dirname [file dirname [info script]]]',script)
            for rel in ('hardware/ecg_system_candidate.bit','hardware/ps7_init.tcl','prebuilt/ecg_'+name+'.elf'):
                self.assertTrue((CANDIDATE/name/rel).is_file())

    def test_only_manifest_files_are_unignored(self):
        lines=(ROOT/'.gitignore').read_text().splitlines()
        self.assertNotIn('!/releases/latest/**',lines)
        files=set(json.loads((CANDIDATE/'manifest.json').read_text())['files'])|{'manifest.json'}
        explicit={line.removeprefix('!/releases/latest/') for line in lines
                  if line.startswith('!/releases/latest/') and not line.endswith('/')}
        self.assertEqual(explicit,files)
        for d in ('smoke','bridge','smoke/hardware','bridge/prebuilt'):
            self.assertIn('/releases/latest/'+d+'/*',lines)


if __name__=='__main__':unittest.main()
