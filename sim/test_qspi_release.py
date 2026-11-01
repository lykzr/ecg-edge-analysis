"""QSPI交付的组成绑定、可写目录检查与篡改拒绝；不操作板卡。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'releases/latest'


class QspiReleaseTests(unittest.TestCase):
    def test_boot_inputs_bind_to_actual_programming_receipt(self):
        meta=json.loads((PACKAGE/'qspi/manifest.json').read_text())
        receipt=json.loads((ROOT/'data/results/session_reuse_release_20261101.json').read_text())
        for name,expected in meta['components'].items():
            path=PACKAGE/expected['path'];data=path.read_bytes()
            self.assertEqual(len(data),expected['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),expected['sha256'])
        boot=(PACKAGE/'qspi/BOOT.BIN').read_bytes()
        self.assertEqual(boot[32:40],bytes.fromhex('665599aa584e4c58'))
        self.assertEqual(hashlib.sha256(boot).hexdigest(),receipt['boot_sha256'])
        self.assertTrue(receipt['cold_boot_user_confirmed'])
        self.assertEqual(receipt['boot_mode'],1)
        self.assertFalse(receipt['cold_boot_jtag_download_used'])
        sessions=json.loads((ROOT/receipt['qspi_sessions']).read_text())
        self.assertEqual(sessions['sessions'][-1]['info']['confirmed'],5000)

    def test_reset_does_not_download_or_reconfigure(self):
        script=(PACKAGE/'qspi/reset_qspi.tcl').read_text(encoding='utf-8')
        commands='\n'.join(s for s in script.splitlines() if not s.lstrip().startswith('#'))
        self.assertIn('rst -system',commands)
        self.assertNotRegex(commands,r'(?m)^\s*(dow|fpga|ps7_init)\b')
        self.assertIn('set argv [list $cable 1]',commands)

    def test_default_check_and_reject_tampered_component_in_portable_path(self):
        if os.name!='nt':self.skipTest('Windows包装入口需要PowerShell')
        root=ROOT/'tmp/qspi_release_tests';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            target=Path(temp)/'portable folder';shutil.copytree(PACKAGE,target)
            args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(target/'qspi/program_qspi.ps1')]
            result=subprocess.run(args,cwd=temp,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            # 默认不需要下载器、XSDB或板卡；组件与启动镜像分别校验。
            app=target/'runtime500/prebuilt/ecg_runtime500.elf'
            original=app.read_bytes();app.write_bytes(original[:-1]+bytes([original[-1]^1]))
            rejected=subprocess.run(args,cwd=temp,capture_output=True,timeout=30)
            self.assertNotEqual(rejected.returncode,0)
            app.write_bytes(original)
            boot=target/'qspi/BOOT.BIN';blob=boot.read_bytes()
            boot.write_bytes(blob[:-1]+bytes([blob[-1]^1]))
            rejected=subprocess.run(args,cwd=temp,capture_output=True,timeout=30)
            self.assertNotEqual(rejected.returncode,0)


if __name__=='__main__':unittest.main()
