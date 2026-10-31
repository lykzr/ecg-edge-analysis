"""实时接口与离线分析接口分离；全部会话、上传和下载按账户隔离。"""
import asyncio
import json
from typing import Literal
from fastapi import APIRouter, Depends, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.api.auth import current_user
from app.services import family
from ecg_web_service import manager

router = APIRouter(prefix='/live', tags=['实时采集与中转'])


class Start(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['demo', 'log', 'result_serial', 'vendor_csv', 'vendor_serial', 'bridge_csv', 'bridge_serial', 'standard360', 'standard500']
    upload_id: str = Field(default='', max_length=32)
    zynq_port: str = Field(default='', max_length=32)
    zynq_port_identity: str = Field(default='', max_length=512)
    capture_port: str = Field(default='', max_length=32)
    capture_port_identity: str = Field(default='', max_length=512)
    sample_limit: int = Field(default=5000, ge=1, le=1800000, strict=True)
    seconds: float = Field(default=10, ge=1, le=300)
    realtime: StrictBool = True


@router.get('/ports')
def ports(user: str = Depends(current_user)):
    return manager.ports()


@router.post('/uploads')
async def upload(file: UploadFile = File(...), user: str = Depends(current_user)):
    try:
        content = await file.read(manager.MAX_UPLOAD + 1)
        return manager.upload(user, file.filename, content)
    finally:
        await file.close()


@router.post('/sessions', status_code=201)
def start(body: Start, user: str = Depends(current_user)):
    return manager.start(user, body.model_dump())


@router.get('/sessions')
def history(user: str = Depends(current_user)):
    return manager.history(user)


@router.get('/sessions/{identifier}')
def snapshot(identifier: str, user: str = Depends(current_user)):
    return manager.snapshot(user, identifier)


@router.post('/sessions/{identifier}/stop')
def stop(identifier: str, user: str = Depends(current_user)):
    return manager.stop(user, identifier)


@router.get('/sessions/{identifier}/files/{name:path}')
def download(identifier: str, name: str, user: str = Depends(current_user)):
    return FileResponse(manager.file(user, identifier, name), filename=name.split('/')[-1])


@router.get('/sessions/{identifier}/svg')
def svg(identifier: str, user: str = Depends(current_user)):
    return Response(manager.svg(user, identifier), media_type='image/svg+xml',
                    headers={'Content-Disposition': 'attachment; filename="ecg.svg"'})


async def stream(socket: WebSocket, identifier: str):
    # 同源本机服务；令牌放首条消息，不写入URL或访问日志。
    origin = socket.headers.get('origin')
    host = socket.headers.get('host')
    if origin and origin not in {f'http://{host}', f'https://{host}'}:
        await socket.close(code=1008)
        return
    await socket.accept()
    try:
        credentials = await asyncio.wait_for(socket.receive_json(), timeout=5)
        if not isinstance(credentials, dict) or not isinstance(credentials.get('token'), str):
            raise PermissionError('请登录')
        user = await asyncio.to_thread(family.authenticate, credentials['token'])
        while True:
            # 每次检查过期/注销，不让已注销连接继续查看。
            await asyncio.to_thread(family.authenticate, credentials['token'])
            data = await asyncio.to_thread(manager.snapshot, user, identifier)
            await asyncio.wait_for(socket.send_text(json.dumps(data, ensure_ascii=False, allow_nan=False)), timeout=2)
            if not data['active']:
                await socket.close(code=1000)
                return
            await asyncio.sleep(.25)
    except (PermissionError, LookupError, ValueError, asyncio.TimeoutError):
        await socket.close(code=1008)
    except (WebSocketDisconnect, RuntimeError):
        pass


@router.websocket('/sessions/{identifier}/stream')
async def live_stream(socket: WebSocket, identifier: str):
    await stream(socket, identifier)
