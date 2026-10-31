"""实际本机HTTP/WebSocket启动验收；不打开浏览器，不连接设备。"""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from websockets.sync.client import connect


def test_real_local_server(tmp_path):
    project=Path(__file__).resolve().parents[2]
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    env=dict(os.environ,HEALTH_DB_PATH=str(tmp_path/'health.sqlite3'),ECG_UPLOAD_DIR=str(tmp_path/'uploads'),
             ECG_WEB_LIVE_DIR=str(tmp_path/'live'),ECG_MODEL_TYPE='none',ECG_EXPLANATION_PROVIDER='template',PYTHONDONTWRITEBYTECODE='1')
    with (tmp_path/'server.log').open('wb') as output:
        process=subprocess.Popen([sys.executable,'-B',str(project/'src/web/run.py'),'--port',str(port)],cwd=tmp_path,
                                 env=env,stdout=output,stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=2,trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None: raise AssertionError('启动失败：'+(tmp_path/'server.log').read_text(errors='replace'))
                    try:
                        response=client.get('/api/v1/health')
                        if response.status_code==200: break
                    except httpx.TransportError: pass
                    time.sleep(.1)
                else: raise AssertionError('本机服务启动超时')
                assert 'root' in client.get('/live').text
                assert client.get('/api/v1/no-such-api').status_code==404
                user=dict(username='server-test',password='local-test-password')
                assert client.post('/api/v1/auth/register',json=user).status_code==200
                token=client.post('/api/v1/auth/login',json=user).json()['token']
                headers={'Authorization':'Bearer '+token}
                session=client.post('/api/v1/live/sessions',headers=headers,json=dict(kind='demo',seconds=1,realtime=False)).json()['id']
                with connect(f'ws://127.0.0.1:{port}/api/v1/live/sessions/{session}/stream',
                             origin=f'http://127.0.0.1:{port}',open_timeout=2,proxy=None) as stream:
                    stream.send(json.dumps(dict(token=token)))
                    while True:
                        snapshot=json.loads(stream.recv(timeout=3))
                        if not snapshot['active']: break
                assert snapshot['result']['header']['source']=='SYNTH'
                assert snapshot['result']['cls']=='未提供'
                assert len(snapshot['result']['samples'])==360
                raw=client.get(f'/api/v1/live/sessions/{session}/files/raw.log',headers=headers)
                assert raw.status_code==200 and raw.content.startswith(b'H,')
                # 实际multipart上传，再按原日志回放核对。
                upload=client.post('/api/v1/live/uploads',headers=headers,files={'file':('raw.log',raw.content)}).json()['id']
                replay=client.post('/api/v1/live/sessions',headers=headers,json=dict(kind='log',upload_id=upload,realtime=False)).json()['id']
                for _ in range(100):
                    replayed=client.get(f'/api/v1/live/sessions/{replay}',headers=headers).json()
                    if not replayed['active']: break
                    time.sleep(.02)
                assert replayed['result']==snapshot['result']
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=3)
