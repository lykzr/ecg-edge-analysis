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
        result=check(CANDIDATE,ROOT,require_current_sources=False)
        self.assertTrue(result['passed'])
        self.assertEqual(result['cases']['paced']['samples'],60003)
        self.assertFalse(result['hardware_operated'])

    def test_strict_mode_still_rejects_actual_source_drift(self):
        report=check(CANDIDATE,ROOT,require_current_sources=False)
        if report['source_drift']:
            self.assertFalse(report['current_rebuild_qualified'])
            with self.assertRaises(AssertionError):check(CANDIDATE,ROOT)
        else:self.assertTrue(check(CANDIDATE,ROOT)['current_sources_match'])

    def test_tampered_image_rejected(self):
        root=ROOT/'tmp/system_release_tests';root.mkdir(parents=True,exist_ok=True)
        directory=Path(tempfile.mkdtemp(dir=root))/'copy'
        shutil.copytree(CANDIDATE,directory)
        path=directory/'bridge/prebuilt/ecg_bridge.elf'
        data=path.read_bytes();path.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaises((ValueError,AssertionError)):check(directory,ROOT,require_current_sources=False)

    def test_portable_artifacts_use_repository_sources(self):
        root=ROOT/'tmp/system_release_tests';root.mkdir(parents=True,exist_ok=True)
        base=Path(tempfile.mkdtemp(dir=root));directory=base/'portable'
        shutil.copytree(CANDIDATE,directory)
        self.assertTrue(check(directory,ROOT,require_current_sources=False)['passed'])
        self.assertFalse((directory/'src').exists())
        self.assertFalse((directory/'docs').exists())
        self.assertEqual(check(directory,ROOT,require_current_sources=False)['files'],len(json.loads((directory/'manifest.json').read_text())['files'])+1)

    def test_scripts_resolve_package_local_hardware(self):
        for name in ('smoke','bridge')+ (('runtime500',) if (CANDIDATE/'runtime500').exists() else ()):
            script=(CANDIDATE/name/('run_'+name+'.tcl')).read_text()
            self.assertIn('[info script]',script)
            self.assertNotIn('[file dirname [file dirname [info script]]]',script)
            for rel in ('hardware/ecg_system_candidate.bit','hardware/ps7_init.tcl','prebuilt/'+('ecg_runtime500' if name=='runtime500' else 'ecg_'+name)+'.elf'):
                self.assertTrue((CANDIDATE/name/rel).is_file())

    def test_current_release_is_strictly_matched(self):
        report=check(CANDIDATE,ROOT)
        self.assertEqual(report['version'],'20261025-runtime500-qspi-v1')
        self.assertTrue(report['current_sources_match'])
        receipt=json.loads((ROOT/'data/results/runtime500_release_20261025.json').read_text())
        manifest=json.loads((CANDIDATE/'runtime500/manifest.json').read_text())
        self.assertEqual(receipt['production_elf_sha256'],manifest['elf_sha256'])
        self.assertTrue(manifest['adc_source_supported'])

    def test_current_source_mutation_is_still_rejected(self):
        from unittest.mock import patch
        import check_system_release as module
        original=module.digest
        def altered(path):
            return '0'*64 if Path(path)==ROOT/'build/generate_rate500_runtime.py' else original(path)
        with patch.object(module,'digest',side_effect=altered):
            with self.assertRaises(AssertionError):check(CANDIDATE,ROOT)
            report=check(CANDIDATE,ROOT,require_current_sources=False)
            self.assertFalse(report['current_rebuild_qualified']);self.assertTrue(report['source_drift'])

    def test_portable_launcher_checkonly_with_spaces(self):
        import os
        if os.name!='nt':self.skipTest('Windows PowerShell入口仅Windows执行')
        root=ROOT/'tmp/system_release_tests';root.mkdir(parents=True,exist_ok=True)
        base=Path(tempfile.mkdtemp(dir=root));directory=base/'portable folder'
        shutil.copytree(CANDIDATE,directory)
        args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(directory/'runtime500/run_runtime500.ps1'),'-CheckOnly']
        p=subprocess.run(args,cwd=base,capture_output=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        target=directory/'runtime500/prebuilt/ecg_runtime500.elf';data=target.read_bytes();target.write_bytes(data[:-1]+bytes([data[-1]^1]))
        p=subprocess.run(args,cwd=base,capture_output=True,timeout=30)
        self.assertNotEqual(p.returncode,0)
        self.assertIn(b'SHA256',p.stdout+p.stderr)

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
