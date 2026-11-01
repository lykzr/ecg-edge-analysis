"""网页采集链合同：原码、电压和板端输入分别核验，不连接设备。"""
import json
import struct

import numpy as np
import pytest
from scipy.signal import lfilter

from ecg_bridge_capture import NominalConverter
from ecg_capture_core import CaptureWorker, InitialFrames
from ecg_web_service import LiveManager
from test_live import completed


@pytest.mark.parametrize('chunk', [1, 7, 33, 34, 71, 4096])
def test_34_byte_fragmentation_and_channel_order(chunk):
    pairs = [(i - 32, 3000 - i * 123) for i in range(64)]
    payload = b'prefix' + b''.join(
        b'\xaa\xbb' + b''.join(struct.pack('>II', a + 8388608, b + 8388608)
                              for a, b in pairs[start:start + 4])
        for start in range(0, len(pairs), 4))
    parser = InitialFrames()
    decoded = []
    for start in range(0, len(payload), chunk):
        decoded.extend(parser.feed(payload[start:start + chunk]))
    assert decoded == pairs
    assert parser.skipped == 6 and parser.pending == 0


def test_nominal_filter_matches_independent_scipy_and_keeps_block_state():
    codes = [600000 + ((i * 137) % 20000) - 10000 for i in range(1000)]
    converter = NominalConverter(dc_block=True)
    # SciPy在ADC码域独立构造递推，避免混入mV域浮点顺序差异。
    a = 500 / (500 + 2 * np.pi * .5)
    filtered, _ = lfilter([a, -a], [1, -a], np.asarray(codes, dtype=np.float64), zi=[-a * codes[0]])
    actual = []
    for start in range(0, len(codes), 137):
        for code in codes[start:start + 137]:
            converter.convert((12345, code))
            actual.append(converter.output_mv)
    expected = filtered * 2420 / (6 * 8388607)
    np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-10)
    assert actual[0] == 0
    assert NominalConverter.millivolts(codes[0]) != 0
    assert NominalConverter(dc_block=True).convert((0, codes[-1])) == 0


def test_web_voltage_is_unfiltered_ch2_and_original_is_downloadable(tmp_path):
    manager = LiveManager(tmp_path / 'live', port_enumerator=lambda: ([], []))
    codes = [-8388608, -20800, 0, 20800, 8388607]
    content = ('timestamp(s),resp_raw,ecg_raw,resp_filtered,ecg_filtered\n' +
               '\n'.join(f'{i/500:.3f},8388731,{code+8388608},999999,-999999'
                         for i, code in enumerate(codes))).encode()
    upload = manager.upload('owner', 'raw.csv', content)
    try:
        identifier = manager.start('owner', dict(kind='vendor_csv', upload_id=upload['id'], realtime=False))['id']
        snapshot = completed(manager, 'owner', identifier)
        assert snapshot['info']['error'] is None
        assert [s['ecg_nominal_mv'] for s in snapshot['source_samples']] == [
            code * 2420 / (6 * 8388607) for code in codes]
        assert [s['ecg_raw'] for s in snapshot['source_samples']] == [code + 8388608 for code in codes]
        assert snapshot['source_samples'][0]['ecg_nominal_mv'] < -400
        assert manager.file('owner', identifier, 'source.csv').read_bytes() == content
        nominal = manager.file('owner', identifier, 'nominal.csv').read_text().splitlines()
        assert float(nominal[1].split(',')[3]) == 0  # 板端去直流首点与来源电压分开。
        assert snapshot['capture_info']['source_drop'] is None
    finally:
        manager.shutdown()


def test_corrupt_locked_frame_retains_bytes_and_stops(tmp_path):
    frame = b'\xaa\xbb' + struct.pack('>II', 8388608, 8388608) * 4
    bad = b'\xaa\xbb' + struct.pack('>II', 0x1000000, 8388608) * 4
    chunks = iter([frame * 3, bad])
    class Port:
        closed = False
        def read(self, size): return next(chunks, b'')
        def close(self): self.closed = True
    port = Port()
    worker = CaptureWorker('serial', 'fake', tmp_path / 'capture', normalization='nominal500',
                           serial_factory=lambda *args: port, idle_timeout=.1)
    worker.start()
    worker.join(3)
    if worker.is_alive():
        worker.stop(); worker.join(2)
    info, _ = worker.snapshot()
    assert not worker.is_alive() and port.closed
    assert info['state'] == 'error' and '高8位' in info['error']
    assert info['total'] == 12
    assert (worker.directory / 'capture.bin').read_bytes() == frame * 3 + bad
    assert json.loads((worker.directory / 'summary.json').read_text(encoding='utf-8'))['error']


def test_uploaded_raw_is_linked_before_task_can_execute(client, monkeypatch):
    from app.core.runner import runner
    from app.services import records, storage
    from test_api_flow import account
    headers = account(client, 'atomic-raw')
    runner.stop()
    original = records.task_status
    seen = []
    def claim_immediately(user, task_id, **kwargs):
        # 模拟SQLite补取线程在提交后、路由enqueue前立即执行。
        if not seen:
            seen.append(task_id)
            with storage.connect() as db:
                row = db.execute('SELECT input_path FROM analysis_tasks WHERE id=?', (task_id,)).fetchone()
            assert row['input_path']
            assert records.execute(task_id)
        return original(user, task_id, **kwargs)
    monkeypatch.setattr(records, 'task_status', claim_immediately)
    content = b'value\n' + b'0.1\n' * 600
    response = client.post('/api/v1/analyze/ecg', headers=headers,
                           files={'file': ('signal.csv', content)}, data={'sample_rate_hz':'500'})
    assert response.status_code == 202
    task = response.json()
    detail = client.get('/api/v1/records/' + task['record_id'], headers=headers).json()
    assert detail['has_raw_file']
    assert client.get('/api/v1/records/' + task['record_id'] + '/raw', headers=headers).content == content


def test_raw_write_failure_rolls_back_pending_task(client, monkeypatch):
    from pathlib import Path
    from app.services import records, storage
    from test_api_flow import account
    account(client, 'raw-failure')
    with storage.connect() as db:
        owner = db.execute("SELECT id FROM users WHERE username='raw-failure'").fetchone()['id']
    original = Path.open
    def fail_raw(path, *args, **kwargs):
        if path.suffix == '.csv' and args and args[0] == 'xb':
            raise OSError('原件写盘失败注入')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail_raw)
    with pytest.raises(OSError, match='写盘失败'):
        records.submit_task(owner, dict(samples=[0, 1], sample_rate_hz=500), raw_content=b'value\n0\n1\n')
    with storage.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM analysis_tasks WHERE owner_id=?', (owner,)).fetchone()[0] == 0
