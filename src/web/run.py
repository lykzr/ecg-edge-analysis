"""本机网页入口：只绑定回环地址，不默认加载外部模型。"""
from pathlib import Path
import argparse
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TEMP = ROOT / 'tmp/web_runtime/temp'
TEMP.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TEMP)
for directory in (ROOT / 'src', ROOT / 'src/pc', ROOT / 'src/web', ROOT / 'src/web/business_logic'):
    sys.path.insert(0, str(directory))


def create_app(dist=None):
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from app.main import app
    dist = Path(dist or ROOT / 'tmp/web_frontend/dist').resolve()
    if (dist / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='web-assets')

    @app.get('/{path:path}', include_in_schema=False)
    def page(path: str):
        if path == 'api' or path.startswith('api/'):
            return JSONResponse({'detail': '接口不存在'}, status_code=404)
        if not (dist / 'index.html').is_file():
            return JSONResponse({'detail': '请先运行 build/build_web.ps1 构建网页'}, status_code=503)
        return FileResponse(dist / 'index.html')
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ECG网页客户端（本机单进程）')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('端口须为1024至65535')
    import uvicorn
    print(f'浏览器打开 http://127.0.0.1:{args.port}；首次使用先注册本地账号；Ctrl+C停止并保存。')
    uvicorn.run(create_app(), host='127.0.0.1', port=args.port, workers=1, ws='websockets-sansio')
