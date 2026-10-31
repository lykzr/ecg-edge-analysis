"""网页适配集成；模拟串口与真实C软件核心不替代板卡/无线验收。"""
import json
import time
from pathlib import Path

import pytest
from starlette.websockets import WebSocketDisconnect
from ecg_web_service import LiveManager, MonitorWorker
from app.api import live
from test_api_flow import account


@pytest.fixture
def manager(tmp_path, monkeypatch):
    instance = LiveManager(tmp_path / 'live', port_enumerator=lambda: ([], []))
    monkeypatch.setattr(live, 'manager', instance)
    monkeypatch.setattr('ecg_web_service.remember_identity', lambda *args, **kwargs: None)
    yield instance
    instance.shutdown()


def completed(manager, owner, identifier):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = manager.snapshot(owner, identifier)
        if not snapshot['active']:
            return snapshot
        time.sleep(.01)
    raise AssertionError('后台未结束')


def test_demo_raw_replay_and_unknown_class(manager):
    identifier = manager.start('a', {'kind':'demo', 'seconds':2, 'realtime':False})['id']
    demo = completed(manager, 'a', identifier)
    assert demo['result']['cls'] == '未提供'
    assert demo['result']['hr'] == 75
    assert demo['result']['header']['source'] == 'SYNTH'
    assert len(demo['result']['samples']) == 720
    assert demo['result']['samples'][0]['index'] == 0
    raw = manager.file('a', identifier, 'raw.log').read_bytes()
    upload = manager.upload('a','raw.log', raw)
    replay_id = manager.start('a', {'kind':'log', 'upload_id':upload['id'], 'realtime':False})['id']
    replay = completed(manager, 'a', replay_id)
    assert replay['result'] == demo['result']
    for filename in ('raw.log','samples.csv','events.csv','status.csv','sessions.jsonl'):
        assert manager.file('a', identifier, filename).read_bytes() == manager.file('a', replay_id, filename).read_bytes()
    assert 'SYNTH' in manager.svg('a', identifier)


def test_owner_and_path_isolation(manager):
    upload = manager.upload('a','source.csv',b'value\n1\n')
    with pytest.raises(LookupError): manager.start('b',dict(kind='vendor_csv',upload_id=upload['id']))
    identifier = manager.start('a',dict(kind='demo',seconds=1,realtime=False))['id']
    completed(manager,'a',identifier)
    with pytest.raises(LookupError): manager.snapshot('b',identifier)
    with pytest.raises(LookupError): manager.file('a',identifier,'../../../AGENTS.md')
    assert manager.history('b') == []


def test_stop_busy_and_reopen(manager):
    identifier = manager.start('a',dict(kind='demo',seconds=60))['id']
    with pytest.raises(ValueError,match='已有'): manager.start('a',dict(kind='demo'))
    stopped = manager.stop('a',identifier)
    assert not stopped['active']
    assert stopped['info']['reason'] == 'stopped_by_user'
    next_id = manager.start('a',dict(kind='demo',seconds=1,realtime=False))['id']
    completed(manager,'a',next_id)
    manager.shutdown(); manager.reopen()
    identifier = manager.start('a',dict(kind='demo',seconds=1,realtime=False))['id']
    completed(manager,'a',identifier)


def test_vendor_preserves_raw_and_declares_conversion(manager):
    content = ('timestamp(s),resp_raw,ecg_raw,resp_filtered,ecg_filtered\n' +
               '\n'.join(f'{7+i/500:.3f},8388608,{8388608+i},0,0' for i in range(120))).encode()
    upload = manager.upload('a','capture.csv',content)
    identifier = manager.start('a',dict(kind='vendor_csv',upload_id=upload['id'],realtime=False))['id']
    snapshot = completed(manager,'a',identifier)
    assert snapshot['info']['error'] is None
    assert snapshot['capture_info']['conversion']['pga_gain'] == 6
    assert snapshot['source_samples'][0]['ecg_raw'] == 8388608
    assert snapshot['result']['hr'] is None
    assert manager.file('a',identifier,'source.csv').read_bytes() == content


def test_invalid_vendor_rate_is_error_and_saved(manager):
    content = b'timestamp(s),resp_raw,ecg_raw,resp_filtered,ecg_filtered\n0,8388608,8388608,0,0\n0.004,8388608,8388608,0,0\n'
    upload = manager.upload('a','capture.csv',content)
    identifier = manager.start('a',dict(kind='vendor_csv',upload_id=upload['id'],realtime=False))['id']
    snapshot = completed(manager,'a',identifier)
    assert snapshot['info']['error']
    assert 'summary.json' in snapshot['files']


def test_disk_history_survives_manager_restart(manager):
    identifier = manager.start('a',dict(kind='demo',seconds=1,realtime=False))['id']
    completed(manager,'a',identifier)
    path = manager.directory/'sessions'/identifier/'web_meta.json'
    deadline = time.monotonic()+2
    while not path.exists() and time.monotonic()<deadline: time.sleep(.01)
    restarted = LiveManager(manager.directory)
    assert restarted.snapshot('a',identifier)['active'] is False
    assert restarted.history('a')[0]['id'] == identifier
    assert restarted.history('b') == []
    assert restarted.file('a',identifier,'raw.log').is_file()


def test_snapshot_save_failure_is_visible_and_raw_retained(manager, monkeypatch):
    original = Path.replace
    def fail_snapshot(path, target):
        if path.name == 'web_session.new':
            raise OSError('快照保存故障注入')
        return original(path, target)
    monkeypatch.setattr(Path, 'replace', fail_snapshot)
    identifier = manager.start('a',dict(kind='demo',seconds=1,realtime=False))['id']
    completed(manager,'a',identifier)
    manager.jobs[identifier]['watcher'].join(2)
    snapshot = manager.snapshot('a',identifier)
    assert '保存故障' in snapshot['persistence_error']
    assert manager.file('a',identifier,'raw.log').read_bytes().startswith(b'H,')


def test_usb_identity_and_same_port_are_rejected(manager):
    manager.port_enumerator = lambda: ([dict(port='COM9',device_id='usb-board',candidate=True)],[])
    with pytest.raises(ValueError,match='身份'): manager.start('a',dict(kind='result_serial',zynq_port='COM9'))
    with pytest.raises(ValueError,match='身份'): manager.start('a',dict(kind='result_serial',zynq_port='COM9',zynq_port_identity='old-device'))
    with pytest.raises(ValueError,match='冲突'): manager.start('a',dict(kind='bridge_serial',zynq_port='COM9',zynq_port_identity='usb-board',capture_port='COM9',capture_port_identity='usb-board'))


def test_port_suggestions_do_not_share_one_usb(manager, monkeypatch):
    monkeypatch.setattr('ecg_web_service.remembered_identity', lambda role: '')
    manager.port_enumerator = lambda: ([dict(port='COM9',device_id='usb-board',candidate=True)],[])
    ports = manager.ports()
    assert ports['zynq'] == 'COM9'
    assert ports['capture'] == ''


def test_upload_limits_and_no_arbitrary_server_path(manager):
    with pytest.raises(ValueError): manager.upload('a','file.exe',b'123')
    with pytest.raises(ValueError): manager.upload('a','file.csv',b'')
    manager.MAX_UPLOAD = 32
    with pytest.raises(ValueError): manager.upload('a','file.csv',b'x'*33)
    with pytest.raises(LookupError): manager.start('a',dict(kind='log',upload_id=str(Path.cwd()/'AGENTS.md')))


def test_api_authenticated_demo_upload_download_and_socket(manager, client):
    a, b = account(client,'live-a'), account(client,'live-b')
    assert client.get('/api/v1/live/ports').status_code == 401
    response = client.post('/api/v1/live/sessions',headers=a,json=dict(kind='demo',seconds=1,realtime=False))
    assert response.status_code == 201
    identifier = response.json()['id']
    with client.websocket_connect(f'/api/v1/live/sessions/{identifier}/stream') as socket:
        socket.send_json(dict(token=a['Authorization'].split()[1]))
        data = socket.receive_json()
        assert data['id'] == identifier
    completed(manager,next(iter(manager.jobs.values()))['owner'],identifier)
    assert client.get(f'/api/v1/live/sessions/{identifier}',headers=b).status_code == 404
    raw = client.get(f'/api/v1/live/sessions/{identifier}/files/raw.log',headers=a)
    assert raw.status_code == 200 and raw.content.startswith(b'H,')
    svg = client.get(f'/api/v1/live/sessions/{identifier}/svg',headers=a)
    assert svg.status_code == 200 and '<svg' in svg.text
    upload = client.post('/api/v1/live/uploads',headers=a,files={'file':('raw.log',raw.content)}).json()
    assert upload['bytes'] == len(raw.content)
    assert client.post('/api/v1/live/sessions',headers=b,json=dict(kind='log',upload_id=upload['id'])).status_code == 404


def test_socket_wrong_owner_origin_and_missing_session(manager, client):
    a,b = account(client,'socket-a'),account(client,'socket-b')
    identifier = client.post('/api/v1/live/sessions',headers=a,json=dict(kind='demo',seconds=1,realtime=False)).json()['id']
    with client.websocket_connect(f'/api/v1/live/sessions/{identifier}/stream') as socket:
        socket.send_json(dict(token=b['Authorization'].split()[1]))
        with pytest.raises(WebSocketDisconnect): socket.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f'/api/v1/live/sessions/{identifier}/stream',headers={'origin':'https://other.example'}): pass
    with client.websocket_connect('/api/v1/ws/realtime?session_id='+'a'*32) as socket:
        socket.send_json(dict(token=a['Authorization'].split()[1]))
        with pytest.raises(WebSocketDisconnect): socket.receive_json()


def test_serial_failure_closes_and_records(tmp_path):
    class Broken:
        closed = False
        def read(self,size): raise OSError('断连注入')
        def close(self): self.closed=True
    port = Broken()
    worker = MonitorWorker('result_serial','COM9',tmp_path/'serial',serial_factory=lambda *args:port)
    worker.start(); worker.join(2)
    assert not worker.is_alive() and port.closed
    assert '断连' in worker.snapshot()[0]['error']
    assert json.loads((tmp_path/'serial/summary.json').read_text(encoding='utf-8'))['reason']=='error'


def test_task_queue_is_bounded_and_overflow_remains_durable():
    from app.core.runner import TaskRunner
    runner = TaskRunner()
    for index in range(128): assert runner.enqueue(str(index))
    assert runner.enqueue('extra') is False
    assert runner.queue.qsize()==128


def test_queue_overflow_reloaded_from_sqlite(client):
    from app.core.runner import TaskRunner, runner
    from app.services import records, storage
    headers=account(client,'overflow-owner')
    runner.stop()
    with storage.connect() as db:
        owner=db.execute('SELECT id FROM users WHERE username=?',('overflow-owner',)).fetchone()['id']
    task=records.submit(owner,dict(samples=[1,2],sample_rate_hz=500,unit='mV',source='test'))
    bounded=TaskRunner()
    for index in range(128): bounded.enqueue('dummy-'+str(index))
    assert bounded.enqueue(task['id']) is False
    assert records.task_status(owner,task['id'])['status']=='pending'
    bounded.start()
    try:
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            status=records.task_status(owner,task['id'])
            if status['status']=='completed': break
            time.sleep(.02)
        assert status['status']=='completed'
    finally: bounded.stop()


def test_request_body_cap_includes_chunked_upload():
    import asyncio
    from app.core.body_limit import BodyLimit
    async def run():
        messages=iter([dict(type='http.request',body=b'123',more_body=True),dict(type='http.request',body=b'456',more_body=False)])
        async def receive(): return next(messages)
        sent=[]
        async def send(message): sent.append(message)
        async def app(scope,receive,send):
            while (await receive()).get('more_body'): pass
        await BodyLimit(app,maximum=5)({'type':'http'},receive,send)
        assert sent[0]['status']==413
    asyncio.run(run())
