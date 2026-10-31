"""同源静态网页入口，不依赖打开浏览器。"""
import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient


def test_static_spa_and_unknown_api(tmp_path):
    project=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('ecg_web_launch',project/'src/web/run.py')
    launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)
    (tmp_path/'assets').mkdir()
    (tmp_path/'assets/app.js').write_text('/* 仅测试静态资源 */',encoding='utf-8')
    (tmp_path/'index.html').write_text('<!doctype html><title>ECG</title>',encoding='utf-8')
    app=launch.create_app(tmp_path)
    # 不启动业务生命周期；这里只核对SPA路由及API隔离。
    client=TestClient(app)
    assert client.get('/live').status_code==200
    assert '<title>ECG</title>' in client.get('/records/abc').text
    assert client.get('/assets/app.js').status_code==200
    assert client.get('/api/v1/unknown').status_code==404
