"""获得临时板测授权后执行真实HTTP/串口CNN→HGB→CNN切换；不复位、不写Flash。"""
import argparse, hashlib, json, os, secrets, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(port, device_id, source, output, streaming=False,stop_after=0):
    output = Path(output).resolve()
    output.relative_to(ROOT / 'tmp')
    output.mkdir(parents=True, exist_ok=False)
    os.environ.update(HEALTH_DB_PATH=str(output/'web.sqlite3'),
        ECG_UPLOAD_DIR=str(output/'uploads'), ECG_WEB_LIVE_DIR=str(output/'live'),
        ECG_MODEL_TYPE='none', ECG_EXPLANATION_PROVIDER='template')
    sys.path.insert(0, str(ROOT/'src/web'))
    from run import create_app
    from fastapi.testclient import TestClient
    from ecg_ports import enumerate_ports
    from ecg_web_service import manager
    ports, _ = enumerate_ports()
    assert sum(p['port']==port and p['device_id']==device_id for p in ports)==1, 'USB身份不匹配'
    checks = []
    with TestClient(create_app()) as client:
        credentials = dict(username='board-check', password=secrets.token_urlsafe(24))
        assert client.post('/api/v1/auth/register', json=credentials).status_code==200
        token = client.post('/api/v1/auth/login', json=credentials).json()['token']
        headers = {'Authorization': 'Bearer '+token}
        upload = client.post('/api/v1/live/uploads', headers=headers,
            files={'file': ('controlled.csv', Path(source).read_bytes(), 'text/csv')})
        assert upload.status_code==200, upload.text
        for number, classifier in enumerate(('cnn','hgb','cnn')):
            stream_mode=streaming and number!=1
            response = client.post('/api/v1/live/sessions', headers=headers, json=dict(
                kind='bridge_csv', upload_id=upload.json()['id'], zynq_port=port,
                zynq_port_identity=device_id, realtime=stream_mode, board_model=True,
                board_classifier=classifier, board_streaming=stream_mode, analyze_when_complete=False))
            assert response.status_code==201, response.text
            identifier = response.json()['id']
            endpoint = '/api/v1/live/sessions/'+identifier
            deadline = time.monotonic()+120
            live_results=[]
            stop_sent=False
            while time.monotonic()<deadline:
                response = client.get(endpoint, headers=headers)
                assert response.status_code==200, response.text
                snapshot = response.json()
                if snapshot['active'] and snapshot['result']['events']:live_results.append(snapshot['info']['confirmed'])
                if number==0 and stream_mode and stop_after and not stop_sent and snapshot['info']['confirmed']>=stop_after:
                    assert client.post(endpoint+'/stop',headers=headers).status_code==200
                    stop_sent=True
                if not snapshot['active']: break
                time.sleep(.25)
            else:
                client.post(endpoint+'/stop', headers=headers)
                raise TimeoutError('网页板端分类超时')
            (output/f'snapshot_{number}.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            info = snapshot['info']
            assert not info['error'] and info['reason']==('stopped_by_user' if stop_sent else 'completed'), info
            assert info['execution_location']=='zynq_pl' and info['classifier']==classifier
            assert info['source_samples']==info['confirmed']
            assert info['performance']['mismatches']==0
            if stream_mode:
                assert live_results and min(live_results)<info['confirmed'], '结束前网页没有分类结果'
                assert info['streaming'] and snapshot['result']['events'][-1]['arm_us']>0
            assert info['performance']['beats']==sum(v for k,v in info['class_counts'].items() if k!='UNCLASSIFIED')
            svg = client.get(endpoint+'/svg',headers=headers)
            assert svg.status_code==200 and '<polyline' in svg.text
            assert client.get(endpoint+'/files/result.json',headers=headers).status_code==200
            checks.append(dict(classifier=classifier, streaming=stream_mode, live_results=live_results, samples=info['confirmed'],
                counts=info['class_counts'], performance=info['performance'],
                directory=str(manager.jobs[identifier]['directory'].relative_to(ROOT))))
        assert client.get('/').status_code==200
    result = dict(passed=True, source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        checks=checks, no_reset_between_sessions=True, flash_written=False,
        scope='真实HTTP接口及USB_UART；不代替浏览器人工验收或持续采样验证')
    (output/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('port','device-id','source','output'): p.add_argument('--'+name,required=True)
    p.add_argument('--streaming',action='store_true')
    p.add_argument('--stop-after',type=int,default=0)
    a=p.parse_args(); run(a.port,a.device_id,a.source,a.output,a.streaming,a.stop_after)
