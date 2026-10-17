"""离线核对交接 ZIP 的内容、哈希、相对启动路径及 XSA/bit 组合。"""
import argparse
import hashlib
import io
import json
from pathlib import PurePosixPath
import zipfile


def check(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names)), '重复 ZIP 条目'
        roots = {PurePosixPath(n).parts[0] for n in names}
        assert len(roots) == 1
        prefix = next(iter(roots)) + '/'
        for name in names:
            parts = PurePosixPath(name).parts
            assert not PurePosixPath(name).is_absolute() and '..' not in parts
        manifest = json.loads(archive.read(prefix + 'manifest.json'))
        assert manifest['board_execution'] == 'NOT_TESTED'
        assert set(names) == {prefix + n for n in manifest['files']} | {prefix + 'manifest.json'}
        for name, entry in manifest['files'].items():
            payload = archive.read(prefix + name)
            assert len(payload) == entry['bytes']
            assert hashlib.sha256(payload).hexdigest() == entry['sha256'], name
            if name.endswith(('.py', '.ps1', '.tcl', '.json')):
                assert 'C:/Users/23006' not in payload.decode('utf-8').replace('\\', '/')
        bit = archive.read(prefix + 'hardware/ecg_system_candidate.bit')
        with zipfile.ZipFile(io.BytesIO(archive.read(prefix + 'hardware/ecg_system_candidate.xsa'))) as xsa:
            assert xsa.read('ecg_system_candidate.bit') == bit, 'XSA 和 bit 不匹配'
        launch = json.loads(archive.read(prefix + 'board/launch_template.json'))['configurations'][0]
        setup = launch['targetSetup']
        assert setup['resetSystem'] and setup['programDevice']
        assert setup['zynqInitialization']['usingPs7Init']['runPs7Init']
        assert setup['zynqInitialization']['usingPs7Init']['runPs7PostInit']
        assert not setup['zynqInitialization']['isFsbl']
        assert len(setup['downloadElf']) == 1
        assert setup['downloadElf'][0]['core'] == 'ps7_cortexa9_0'
        assert not setup['downloadElf'][0]['stopAtEntry']
        assert setup['bitstreamFile'].startswith('${workspaceFolder}')
        assert 'BOOT.BIN' not in [PurePosixPath(n).name for n in names]
        print('PASS: ZIP/全部文件SHA256/路径/XSA内嵌bit/GUI复位与配置；未操作硬件')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    check(parser.parse_args().archive)
