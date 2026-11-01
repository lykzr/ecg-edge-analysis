"""真实HGB子进程与HTTP/采集整段接入，不训练、不使用患者数据或板卡。"""
import csv
import io
from pathlib import Path
import time

import numpy as np
import pytest

from ai_model.inference.hgb_adapter import HgbClassifier, associate_board_events
from ai_model.pipeline import analyze
from app.api import live
from app.services import storage
from ecg_web_service import LiveManager
from test_api_flow import account, wait_task
from test_live_board import library, Node

PROJECT = Path(__file__).resolve().parents[2]
MODULE = PROJECT / 'model/inference'


def test_analysis_route_registered_once():
    routes = [r for r in live.router.routes if getattr(r, 'path', None) == '/live/sessions/{identifier}/analyze'
              and 'POST' in getattr(r, 'methods', set())]
    assert len(routes) == 1


@pytest.fixture
def synthetic():
    return np.loadtxt(MODULE / 'examples/synthetic500.csv', delimiter=',')


def test_real_worker_matches_frozen_all_beats_and_probabilities(monkeypatch, synthetic):
    monkeypatch.setenv('ECG_MODEL_TYPE', 'hgb')
    result = analyze(dict(samples=synthetic.tolist(), sample_rate_hz=500, unit='mV'))
    prediction = result['prediction']
    assert result['mode'] == 'hgb-beat-pipeline'
    assert prediction['status'] == 'classified'
    assert prediction['task_type'] == 'beat_level' and prediction['execution_location'] == 'host_pc'
    assert prediction['qualified'] is False and prediction['confidence'] is None
    assert prediction['beats']['count'] == 73 and prediction['beats']['classified_count'] == 72
    items = prediction['beats']['items']
    with np.load(MODULE / 'examples/synthetic_expected.npz', allow_pickle=False) as golden:
        np.testing.assert_array_equal([b['r_sample500'] for b in items], golden['positions500'])
        np.testing.assert_array_equal([b['valid'] for b in items], golden['valid'])
        np.testing.assert_array_equal([b['decision_sample500'] for b in items], golden['decision_at'])
        np.testing.assert_allclose([b['probabilities'] for b in items if b['valid']],
                                   golden['probability_0'][golden['valid']], rtol=1e-12, atol=1e-12)
    assert items[0]['label'] == 'UNCLASSIFIED' and items[0]['probabilities'] is None
    assert 'vpc_count' not in prediction['beats']
    assert 'VF为V/E/F合并' in prediction['explanation_detail']['professional_interpretation']


@pytest.mark.parametrize('rate,unit', [(360, 'mV'), (500, 'ADC')])
def test_wrong_input_is_unavailable_not_normal(rate, unit):
    result = HgbClassifier().predict(dict(sample_rate_hz=rate, unit=unit, waveform_raw_mV=[1.0]*1000))
    assert result['status'] == 'model_unavailable' and result['label'] is None


def test_failed_model_process_does_not_emit_a_label():
    model = HgbClassifier(python='missing-hgb-python-executable')
    result = model.predict(dict(sample_rate_hz=500, unit='mV', waveform_raw_mV=[0.1]*1000))
    assert result['status'] == 'model_unavailable' and result['confidence'] is None


def test_fixed_unique_board_association_preserves_ambiguity():
    beats = [dict(r_sample500=p) for p in [100, 200, 225, 400]]
    result = associate_board_events(beats, [dict(event_id=i, r_sample500=p) for i, p in enumerate([110, 210, 480])])
    assert result['matched'] == 1
    assert beats[0]['board_event_id'] == 0 and beats[0]['board_delta_samples'] == -10
    assert beats[1]['board_association'] == beats[2]['board_association'] == 'ambiguous'
    assert beats[3]['board_event_id'] is None


def test_unavailable_explanation_does_not_report_zero_abnormal_beats():
    from ai_model.explanation.concepts import build_evidence_payload
    from ai_model.explanation.generator import generate_explanation
    prediction = dict(task_type='beat_level', status='model_unavailable', label=None,
                      confidence=None, explanation='HGB环境或文件校验失败。')
    explanation = generate_explanation(build_evidence_payload(prediction, {'status':'basic_checks_passed'}))
    assert explanation['summary'] == prediction['explanation']
    assert 'N 0' not in explanation['summary']


def test_http_upload_executes_real_hgb_and_export(client, monkeypatch, synthetic):
    monkeypatch.setenv('ECG_MODEL_TYPE', 'hgb')
    headers = account(client, 'hgb-upload')
    response = client.post('/api/v1/analyze/ecg', headers=headers,
        files={'file': ('mv.csv', (MODULE/'examples/synthetic500.csv').read_bytes())}, data={'sample_rate_hz': '500'})
    assert response.status_code == 202
    task = wait_task(client, headers, response.json()['id'], timeout=30)
    assert task['status'] == 'completed'
    prediction = task['record']['result']['prediction']
    assert prediction['beats']['classified_count'] == 72
    exported = client.get('/api/v1/records/'+task['record_id']+'/export?format=json', headers=headers)
    assert exported.status_code == 200 and 'r_sample500' in exported.text


def test_complete_capture_auto_analysis_uses_all_ch2_and_survives_restart(client, monkeypatch, tmp_path, synthetic):
    monkeypatch.setenv('ECG_MODEL_TYPE', 'hgb')
    manager = LiveManager(tmp_path / 'live', port_enumerator=lambda: ([], []))
    monkeypatch.setattr(live, 'manager', manager)
    headers = account(client, 'hgb-capture')
    raw_codes = np.rint(synthetic * (6 * 8388607) / 2420).astype(int) + 8388608
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(['timestamp(s)', 'resp_raw', 'ecg_raw', 'resp_filtered', 'ecg_filtered'])
    # 非零起始时间及故意无关厂商滤波列，证明不混用幅值或时轴。
    for i, raw in enumerate(raw_codes):
        writer.writerow([7+i/500, 8388608, raw, 999999, -999999])
    try:
        upload = client.post('/api/v1/live/uploads', headers=headers, files={'file':('source.csv', output.getvalue().encode())})
        response = client.post('/api/v1/live/sessions', headers=headers,
            json=dict(kind='vendor_csv', upload_id=upload.json()['id'], realtime=False))
        assert response.status_code == 201
        identifier = response.json()['id']
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            snapshot = client.get('/api/v1/live/sessions/'+identifier, headers=headers).json()
            if not snapshot['active'] and snapshot['analysis']['status'] != 'waiting':
                break
            time.sleep(.02)
        assert snapshot['analysis']['status'] == 'submitted', snapshot
        task = wait_task(client, headers, snapshot['analysis']['task_id'], timeout=30)
        assert task['status'] == 'completed', task
        record = task['record']
        assert record['n_samples'] == len(synthetic) > len(snapshot['source_samples']) == 4096
        assert record['result']['prediction']['status'] == 'classified'
        assert record['result']['prediction']['preprocess'] == 'hp05'
        assert record['result']['source_session_id'] == identifier
        assert client.get('/api/v1/live/sessions', headers=headers).json()[0]['analysis_count'] == 1
        versions = client.get('/api/v1/live/sessions/'+identifier+'/analyses', headers=headers).json()
        assert any(v['record_id'] == task['record_id'] for v in versions)
        with storage.connect() as db:
            payload = db.execute('SELECT payload FROM task_inputs WHERE task_id=?', (task['id'],)).fetchone()[0]
        import json
        submitted = json.loads(payload)
        np.testing.assert_allclose(submitted['samples'], (raw_codes-8388608)*2420/(6*8388607), rtol=0, atol=1e-15)
        # 重复点击不会生成另一轮推理或重复记录。
        again = client.post('/api/v1/live/sessions/'+identifier+'/analyze', headers=headers, json={})
        assert again.status_code == 202 and again.json()['id'] == task['id']
        # 本地历史列表的无请求体调用也使用同一入口，不生成重复分析。
        again_legacy = client.post('/api/v1/live/sessions/'+identifier+'/analyze', headers=headers)
        assert again_legacy.status_code == 202 and again_legacy.json()['id'] == task['id']
        assert client.get('/api/v1/live/sessions', headers=headers).json()[0]['analysis_count'] == 1
        other = account(client, 'hgb-other')
        assert client.post('/api/v1/live/sessions/'+identifier+'/analyze', headers=other, json={}).status_code == 404
        manager.jobs[identifier]['watcher'].join(3)
        restarted = LiveManager(manager.directory)
        monkeypatch.setattr(live, 'manager', restarted)
        assert restarted.snapshot(submitted_owner(client, headers), identifier)['analysis']['task_id'] == task['id']
    finally:
        manager.shutdown()


def submitted_owner(client, headers):
    # 仅从已认证会话取得真实owner，不能将用户名当数据库主键。
    from app.services.family import authenticate
    return authenticate(headers['Authorization'].split(' ', 1)[1])


@pytest.mark.parametrize('kind', ['bridge_csv', 'standard500'])
def test_actual_ps_c_core_to_http_hgb_preserves_board_unknown(client, monkeypatch, tmp_path, synthetic, library, kind):
    """真实PS C链路经模拟串口返回，再由HTTP采集结束回调提交真实HGB。"""
    from ecg_bridge_worker import BridgeWorker
    monkeypatch.setenv('ECG_MODEL_TYPE', 'hgb')
    monkeypatch.setattr('ecg_web_service.remember_identity', lambda *args: None)
    node = Node(library)
    node.close = lambda: None
    devices = [dict(port='COM9', device_id='board', candidate=True)]
    def factory(kind, source, directory, config):
        if kind == 'standard500':
            from ecg_runtime_worker import RuntimeWorker
            return RuntimeWorker(source, 'COM9', directory, sampling_hz=500,
                port_factory=lambda *args:node, clock=lambda:node.now/1e6, realtime=False)
        return BridgeWorker('csv', source, 'COM9', directory, profile='runtime500',
            port_factory=lambda *args: node, clock=lambda: node.now/1e6, realtime=True, pause=0)
    manager = LiveManager(tmp_path/'board_live', port_enumerator=lambda:(devices, []), worker_factory=factory)
    monkeypatch.setattr(live, 'manager', manager)
    headers = account(client, 'hgb-c-core')
    codes = np.rint(synthetic[:6000] * (6*8388607)/2420).astype(int)+8388608
    content = ('timestamp(s),resp_raw,ecg_raw,resp_filtered,ecg_filtered\n' +
               '\n'.join(f'{i/500},8388608,{raw},0,999999' for i,raw in enumerate(codes))).encode()
    if kind == 'standard500':
        values = np.rint(synthetic[:6000]*4096).astype(int)
        content = ('index,sample,fs,scale\n'+'\n'.join(f'{i},{value},500,4096' for i,value in enumerate(values))).encode()
    try:
        upload = client.post('/api/v1/live/uploads', headers=headers, files={'file':('raw.csv', content)}).json()
        response = client.post('/api/v1/live/sessions', headers=headers,
            json=dict(kind=kind,upload_id=upload['id'],zynq_port='COM9',zynq_port_identity='board',
                      standard_preprocess='hp05' if kind=='standard500' else None))
        assert response.status_code == 201
        identifier = response.json()['id']
        # ctypes逐字节软件串口不是物理设备速度；按网页250ms节奏轮询，
        # 避免序列化4096点快照占满宿主而饿死送样线程。完成条件仍为全部6000点。
        deadline = time.monotonic()+90
        while time.monotonic() < deadline:
            snapshot = client.get('/api/v1/live/sessions/'+identifier, headers=headers).json()
            if not snapshot['active'] and snapshot['analysis']['status'] != 'waiting':
                break
            time.sleep(.25)
        assert not snapshot['active'], snapshot['info']
        assert snapshot['info']['error'] is None, snapshot['info']
        assert snapshot['info']['source_samples'] == snapshot['info']['confirmed'] == snapshot['info']['echoed'] == 6000
        assert snapshot['analysis']['status'] == 'submitted', snapshot['analysis']
        task = wait_task(client, headers, snapshot['analysis']['task_id'], timeout=30)
        assert task['status'] == 'completed', task
        prediction = task['record']['result']['prediction']
        assert prediction['status'] == 'classified' and prediction['execution_location'] == 'host_pc'
        assert prediction['board_association']['matched'] > 0
        assert all(e['cls']=='?' for e in snapshot['result']['events'])
        assert task['record']['result']['acquisition']['board_confirmed'] is True
    finally:
        manager.shutdown()


def test_running_and_failed_capture_not_submitted(client, monkeypatch, tmp_path):
    manager = LiveManager(tmp_path/'reject_live', port_enumerator=lambda:([], []))
    monkeypatch.setattr(live, 'manager', manager)
    headers = account(client, 'hgb-refuse')
    try:
        response = client.post('/api/v1/live/sessions', headers=headers, json=dict(kind='demo',seconds=60))
        identifier = response.json()['id']
        assert client.post('/api/v1/live/sessions/'+identifier+'/analyze', headers=headers, json={}).status_code == 400
        client.post('/api/v1/live/sessions/'+identifier+'/stop', headers=headers)
        assert client.post('/api/v1/live/sessions/'+identifier+'/analyze', headers=headers, json={}).status_code == 400
        assert client.get('/api/v1/records', headers=headers).json() == []
    finally:
        manager.shutdown()
