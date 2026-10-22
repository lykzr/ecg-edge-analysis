"""UI拆分后的启动、依赖方向与新旧入口检查；不打开真实串口。"""
from pathlib import Path
import json
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


class UiLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = ROOT/'tmp/ui_layout_tests'/uuid.uuid4().hex
        cls.output.mkdir(parents=True)

    def run_python(self, args, *, cwd=None):
        result = subprocess.run([sys.executable, '-B', *map(str, args)], cwd=cwd or ROOT,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, (result.stdout+result.stderr).decode(errors='replace'))
        return result

    def test_new_entry_from_other_working_directory(self):
        result = self.run_python([ROOT/'src/ui/main.py', '--help'], cwd=self.output)
        self.assertIn(b'--headless', result.stdout)

    def test_old_entry_from_other_working_directory(self):
        result = self.run_python([ROOT/'src/pc/ecg_monitor.py', '--help'], cwd=self.output)
        self.assertIn(b'--ui-self-test', result.stdout)

    def test_backend_does_not_import_cli_or_ui_or_tk(self):
        source = 'import sys;sys.path.insert(0,'+repr(str(ROOT/'src/pc'))+');'
        source += "import ecg_bridge_worker,ecg_monitor_core;assert 'ecg_bridge' not in sys.modules;"
        source += "assert not any(n=='tkinter' or n.startswith('tkinter.') or n=='ui' or n.startswith('ui.') for n in sys.modules)"
        self.run_python(['-c', source], cwd=self.output)

    def test_new_and_old_entry_headless_outputs_equal(self):
        source = self.output/'source.log'
        source.write_bytes(b'H,ECG-UART-1,layout,s1,SYNTH,SYNTH-MARKERS,500,-1,0xD\n'
                           b'W,0,3,0,NA,120,NA,-20,NA\nE,1,1,0,-1,?,-1\n')
        for name, entry in [('new','src/ui/main.py'),('old','src/pc/ecg_monitor.py')]:
            self.run_python([ROOT/entry,'--headless','--replay',source,'--output-dir',self.output/name],cwd=self.output)
        for name in ('raw.log','samples.csv','events.csv','status.csv','sessions.jsonl','waveform.svg'):
            self.assertEqual((self.output/'new'/name).read_bytes(),(self.output/'old'/name).read_bytes())

    def test_new_and_old_hidden_window_self_test(self):
        try:
            import tkinter
        except ImportError:
            self.skipTest('Tkinter不可用；不冒称人工视觉检查')
        for name,entry in [('new_ui','src/ui/main.py'),('old_ui','src/pc/ecg_monitor.py')]:
            target=self.output/name
            self.run_python([ROOT/entry,'--ui-self-test','--output-dir',target],cwd=self.output)
            self.assertTrue(json.loads((target/'ui_check.json').read_text(encoding='utf-8'))['passed'])


if __name__ == '__main__': unittest.main()
