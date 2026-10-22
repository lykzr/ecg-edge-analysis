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
CANDIDATE=ROOT/'tmp/system_release_20261021/candidate_01'
if not CANDIDATE.exists():
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
        with self.assertRaises(ValueError):check(directory)

    def test_copy_runs_headless_and_preserves_new_old_replay(self):
        root=ROOT/'tmp/system_release_tests';root.mkdir(parents=True,exist_ok=True)
        base=Path(tempfile.mkdtemp(dir=root));directory=base/'portable'
        shutil.copytree(CANDIDATE,directory)
        def run(entry,*args):
            completed=subprocess.run([sys.executable,'-B',str(directory/entry),*map(str,args)],
                                     cwd=base,capture_output=True,text=True,timeout=30)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        run('src/ui/main.py','--headless','--demo','--seconds',1,'--output-dir',base/'demo')
        for folder,entry in [('new','src/ui/main.py'),('old','src/pc/ecg_monitor.py')]:
            run(entry,'--headless','--replay',base/'demo/raw.log','--output-dir',base/folder)
        for n in ('raw.log','samples.csv','events.csv','status.csv','sessions.jsonl','waveform.svg'):
            self.assertEqual((base/'new'/n).read_bytes(),(base/'old'/n).read_bytes(),n)
        run('src/ui/main.py','--ui-self-test','--output-dir',base/'hidden_ui')
        # 运行输出放包外，包内源码/发布清单仍完整。
        self.assertTrue(check(directory)['passed'])

    def test_workspace_wrapper_resolves_package_local_hardware(self):
        path=CANDIDATE/'board/create_bridge_workspace.py'
        spec=importlib.util.spec_from_file_location('workspace_entry',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        values=module.configuration(CANDIDATE)
        self.assertEqual(Path(values['ECG_STREAM_XSA']),CANDIDATE/'bridge/hardware/ecg_system_candidate.xsa')
        self.assertTrue(all(Path(p).is_file() for p in values.values()))


if __name__=='__main__':unittest.main()
