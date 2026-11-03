"""CNN网页四类与HGB分开，确认性能字段不丢失。"""
import json
import ecg_cnn
from ecg_hgb_worker import HgbWorker
from app.api.live import Start
def test_cnn_worker_preserves_four_classes(tmp_path,monkeypatch):
    source=tmp_path/'in.csv';source.write_text('index,sample,fs,scale\n'+''.join(f'{i},0,500,4096\n' for i in range(1000)))
    class Port:
        def __init__(self,*args):pass
        def close(self):pass
    def fake(signal,serial,directory,preprocess,**kw):
        kw['progress'](len(signal),len(signal))
        result=dict(session=8,events=[dict(beat_id=1,position=200,ready_at=466,status=2,label='UNCLASSIFIED',probability=[None]*4),dict(beat_id=2,position=600,ready_at=866,status=0,label='F',probability=[.1,.1,.1,.7])],compute_us={},clipped=0,execution_location='zynq_pl',performance=dict(scope='full_cnn_network',beats=1,mismatches=0),precision='FP32')
        (directory/'result.json').write_text(json.dumps(result));return result
    monkeypatch.setattr(ecg_cnn,'transfer',fake)
    w=HgbWorker('standard500',source,'COMX',tmp_path/'run',preprocess='hp05',realtime=False,port_factory=Port,classifier='cnn')
    w.start();w.join(5);info,_,_,view=w.snapshot()
    assert info['done'] and not info['error'] and info['classifier']=='cnn'
    assert info['model_sha256']==ecg_cnn.MODEL and info['performance']['scope']=='full_cnn_network'
    assert view['cls']=='F' and len(view['events'][-1]['probability'])==4
    assert view['header']['detector']=='CNN-H27-fold0-PL-FP32'
def test_api_model_selection():
    assert Start(kind='bridge_csv',board_classifier='cnn').board_classifier=='cnn'
    assert Start(kind='bridge_csv').board_classifier=='hgb'


def test_int8_selection_is_separate_and_validated(tmp_path):
    import pytest
    from ecg_web_service import LiveManager
    assert Start(kind='bridge_csv',board_classifier='cnn').board_precision=='FP32'
    assert Start(kind='bridge_csv',board_classifier='cnn',board_precision='W8A8').board_precision=='W8A8'
    manager=LiveManager(tmp_path)
    for fields in (dict(board_model=False,board_classifier='cnn'),dict(board_model=True,board_classifier='hgb')):
        with pytest.raises(ValueError,match='INT8'):manager.start('owner',dict(kind='bridge_csv',board_precision='W8A8',**fields))


def test_resource_evidence_pending_no_fabricated_numbers():
    from ecg_accelerator_resources import resources
    result=resources()
    assert result['device']=='xc7z020clg400-2'
    if result['stage']=='pending':assert result['rows']==[] and not result['board_verified']


def test_resource_endpoint_requires_account(client):
    from test_api_flow import account
    assert client.get('/api/v1/live/accelerators').status_code==401
    header=account(client,'resource-reader')
    response=client.get('/api/v1/live/accelerators',headers=header)
    assert response.status_code==200
    assert response.json()['capacity']['bram36']==140

def test_streaming_is_opt_in_and_cnn_only(tmp_path):
    import pytest
    from ecg_web_service import LiveManager
    assert Start(kind='bridge_csv',board_classifier='cnn').board_streaming is False
    assert Start(kind='bridge_csv',board_classifier='cnn',board_streaming=True).board_streaming
    manager=LiveManager(tmp_path)
    for config in (dict(board_model=False,board_classifier='cnn'),dict(board_model=True,board_classifier='hgb')):
        with pytest.raises(ValueError,match='流式'):manager.start('owner',dict(kind='bridge_csv',board_streaming=True,**config))

def test_stream_worker_publishes_before_source_end(tmp_path,monkeypatch):
    import ecg_cnn_live as module
    source=tmp_path/'in.csv';source.write_text('index,sample,fs,scale\n'+''.join(f'{i},0,500,4096\n' for i in range(1000)))
    class Port:
        def __init__(self,*a):pass
        def close(self):pass
    seen=[]
    def fake(blocks,serial,directory,preprocess,limit,*,on_update):
        count=0
        for b in blocks:
            count+=len(b)
            result=dict(samples=count,session=8,events=[],performance=None,compute_us={},clipped=0,wall_seconds=1)
            if count==32:
                on_update(result)
                assert worker.info['source_samples']==32
                assert worker.view['header']['firmware']=='cnn-stream-1'
                seen.append(count)
        result['passed']=True
        (directory/'result.json').write_text(json.dumps(result))
        return result
    monkeypatch.setattr(module,'transfer_stream',fake)
    worker=module.CnnLiveWorker('standard500',source,'COMX',tmp_path/'run',preprocess='hp05',realtime=False,port_factory=Port)
    worker.start();worker.join(5)
    assert not worker.is_alive() and not worker.info['error']
    assert worker.info['confirmed']==1000 and seen==[32]

def test_stream_worker_latest_speedup_and_cumulative_refresh(tmp_path):
    from ecg_cnn_live import CnnLiveWorker
    from ecg_cnn import parse_performance
    worker=CnnLiveWorker('standard500',tmp_path/'in.csv','COMX',tmp_path/'run',preprocess='hp05')
    def event(beat,arm):
        return dict(beat_id=beat,position=beat*400,ready_at=beat*400+100,status=0,label='N',
            probability=[.7,.1,.1,.1],received_through=beat*400+100,host_received_at=0,
            arm_ticks=arm,pl_call_ticks=100,pl_core_ticks=90,feature_ticks=20,
            algorithm_wait_ms=200,arm_class_id=0,pl_class_id=0)
    events=[]
    for beat,arm,total in [(1,200,200),(2,300,500)]:
        events.append(event(beat,arm))
        worker.publish(dict(events=events,samples=1000,session=7,
            performance=parse_performance(f'P,7,FP32,{beat},0,{total},{100*beat},{90*beat},1000000,100000000',7),
            compute_us={},clipped=0))
        info,_,_,view=worker.snapshot()
        assert info['performance']['beats']==beat
        assert info['performance']['call_speedup']==total/(beat*100)
        assert info['latest_performance']==dict(beat_id=beat,call_speedup=arm/100)
        assert view['events'][-1]['arm_us']==arm
