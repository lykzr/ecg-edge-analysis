"""网页板端批处理适配检查；替身仅验证接线，实板另行验收。"""
import json,time
import pytest
import ecg_hgb_worker as module
from ecg_web_service import LiveManager
from app.api.live import Start

def standard(n):
    return ('index,sample,fs,scale\n'+''.join(f'{i},{i%100},500,4096\n' for i in range(n))).encode()

def test_contract_rejects_missing_preprocess(tmp_path):
    manager=LiveManager(tmp_path)
    with pytest.raises(ValueError,match='预处理'):manager.start('a',dict(kind='standard500',board_model=True))
    with pytest.raises(ValueError,match='500Hz'):manager.start('a',dict(kind='demo',board_model=True))
    with pytest.raises(ValueError,match='30000'):manager.start('a',dict(kind='bridge_serial',board_model=True,sample_limit=30001))
    with pytest.raises(Exception):Start(kind='standard500',board_model='yes')

def test_worker_view_and_retained_result(tmp_path,monkeypatch):
    source=tmp_path/'input.csv';source.write_bytes(standard(1000))
    received=[]
    class Port:
        def __init__(self,*args):pass
        def close(self):pass
    def fake(signal,serial,directory,preprocess,**kwargs):
        received.extend(signal);kwargs['progress'](len(signal),len(signal))
        result=dict(session=7,samples=len(signal),model_sha256=module.MODEL,clipped=0,compute_us={'input':1,'prepare':2,'classify':3},
            events=[dict(beat_id=1,position=200,ready_at=466,decision_at=600,status=2,label='UNCLASSIFIED',probability=[None]*3),
                    dict(beat_id=2,position=600,ready_at=866,decision_at=999,status=0,label='VF',probability=[.1,.1,.8])])
        (directory/'result.json').write_text(json.dumps(result));return result
    monkeypatch.setattr(module,'transfer',fake)
    worker=module.HgbWorker('standard500',source,'COMX',tmp_path/'session',preprocess='raw',realtime=False,port_factory=Port)
    worker.start();worker.join(5);assert not worker.is_alive()
    info,ci,samples,view=worker.snapshot()
    assert info['done'] and info['confirmed']==1000 and not info['error']
    assert received[99]==99/4096 and ci['total']==1000
    assert view['cls']=='VF' and view['events'][0]['cls']=='UNCLASSIFIED'
    assert view['hr']==75 and view['rr_ms']==800
    assert view['waveform_origin']=='host_input' and info['execution_location']=='zynq_arm'

def test_excess_csv_not_truncated(tmp_path):
    source=tmp_path/'input.csv';source.write_bytes(standard(30001))
    worker=module.HgbWorker('standard500',source,'COMX',tmp_path/'session',preprocess='hp05',realtime=False)
    worker.start();worker.join(5)
    assert '容量' in worker.info['error'] and not worker.info['done']
    assert not (worker.directory/'result.json').exists()


def test_api_board_mode_and_analysis_separation(tmp_path,monkeypatch,client):
    from app.api import live
    from app.services import live_analysis
    from test_api_flow import account
    manager=LiveManager(tmp_path/'live',port_enumerator=lambda:([dict(port='COMX',device_id='usb-test')],[]))
    monkeypatch.setattr(live,'manager',manager)
    monkeypatch.setattr('ecg_web_service.remember_identity',lambda *args:None)
    class Port:
        def __init__(self,*args):pass
        def close(self):pass
    monkeypatch.setattr(module,'DuplexSerial',Port)
    # 默认参数已绑定原串口类，因此显式替换工作器工厂，保留真实网页管理及文件路径。
    original=module.HgbWorker
    monkeypatch.setattr('ecg_web_service.HgbWorker',lambda *args,**kw:original(*args,**kw,port_factory=Port))
    def transport(signal,serial,directory,preprocess,**kw):
        kw['progress'](len(signal),len(signal))
        result=dict(session=7,samples=len(signal),model_sha256=module.MODEL,clipped=0,compute_us={},events=[])
        (directory/'result.json').write_text(json.dumps(result));return result
    monkeypatch.setattr(module,'transfer',transport)
    headers=account(client,'board-api-owner');other=account(client,'board-api-other')
    upload=client.post('/api/v1/live/uploads',headers=headers,files={'file':('standard.csv',standard(5000))}).json()
    response=client.post('/api/v1/live/sessions',headers=headers,json=dict(kind='standard500',upload_id=upload['id'],
        board_model=True,zynq_port='COMX',zynq_port_identity='usb-test',standard_preprocess='hp05',
        realtime=False,analyze_when_complete=False))
    assert response.status_code==201,response.text
    identifier=response.json()['id'];owner=manager.jobs[identifier]['owner']
    manager.jobs[identifier]['worker'].join(5);manager.jobs[identifier]['watcher'].join(5)
    data=client.get('/api/v1/live/sessions/'+identifier,headers=headers).json()
    assert data['board_model'] and data['info']['execution_location']=='zynq_arm'
    assert data['analysis'] is None and data['result']['waveform_origin']=='host_input'
    assert client.get('/api/v1/live/sessions/'+identifier,headers=other).status_code==404
    assert client.get('/api/v1/live/sessions/'+identifier+'/files/result.json',headers=headers).status_code==200
    assert client.get('/api/v1/live/sessions/'+identifier+'/svg',headers=headers).status_code==200
    captured=[]
    monkeypatch.setattr(live_analysis.records,'submit_analysis',lambda who,signal,**kw:captured.append(signal))
    live_analysis.submit(manager,owner,identifier,standard_preprocess='hp05')
    assert len(captured[0]['samples'])==5000  # 不以4096点显示缓存代替完整输入
    assert captured[0]['acquisition']['board_execution']=='zynq_arm'
    assert captured[0]['acquisition']['model_execution']=='host_pc'
    assert captured[0]['acquisition']['board_waveform_echoed'] is False
    manager.shutdown()
