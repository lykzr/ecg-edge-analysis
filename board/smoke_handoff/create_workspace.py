"""由接收方 Vitis Python 在本机创建工作区；不连接板卡。"""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil

root = Path(__file__).resolve().parents[1]
if any(ord(c) < 33 or ord(c) > 126 for c in str(root)):
    raise RuntimeError('Vitis 工作区需无空格英文路径，例如 D:/ecg_smoke_kit')
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
for name, entry in manifest['files'].items():
    path = root / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
        raise RuntimeError('文件校验失败: ' + name)
workspace = (root / 'workspace').resolve()
os.environ['ECG_SMOKE_WORKSPACE'] = str(workspace)
os.environ['ECG_SMOKE_XSA'] = str(root / 'hardware/ecg_system_candidate.xsa')
runpy.run_path(str(root / 'board/build_ecg_smoke.py'), run_name='__main__')
app = workspace / 'ecg_smoke'
for source, target in [
    ('hardware/ecg_system_candidate.bit', '_ide/bitstream/ecg_system_candidate.bit'),
    ('hardware/ps7_init.tcl', '_ide/psinit/ps7_init.tcl'),
    ('board/launch_template.json', '_ide/launch.json'),
]:
    destination = app / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / source, destination)
print('工作区已创建；在 Vitis Set Workspace 中选择: ' + str(workspace), flush=True)
