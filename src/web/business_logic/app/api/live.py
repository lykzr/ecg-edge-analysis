"""实时接口与离线分析接口分离；全部会话、上传和下载按账户隔离。"""
import asyncio
import json
from typing import Literal
from fastapi import APIRouter, Depends, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.api.auth import current_user
from app.services import family
from app.services import live_analysis
from app.core.runner import runner
from ecg_web_service import manager

router = APIRouter(prefix='/live', tags=['实时采集与中转'])

from app.services.user_files import directory as user_directory
manager.owner_directory = user_directory


def visible_owners(user, shared=False):
    from app.services.storage import connect
    with connect() as db:
        if shared:
            rows = db.execute('SELECT DISTINCT u.id,u.username FROM grants g JOIN users u ON u.id=g.owner_id WHERE g.relative_id=? AND g.active=1', (user,)).fetchall()
        else:
            rows = db.execute('SELECT id,username FROM users WHERE id=?', (user,)).fetchall()
    return [dict(row) for row in rows]


def visible_session(user, identifier):
    for owner in visible_owners(user) + visible_owners(user, True):
        try:
            return owner, manager.snapshot(owner['id'], identifier)
        except LookupError:
            continue
    raise LookupError('会话不存在或没有查看权限')


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
    analyze_when_complete: StrictBool = True
    standard_preprocess: Literal['hp05', 'raw'] | None = None
    board_model: StrictBool = False
    board_classifier: Literal['hgb','cnn'] = 'hgb'
    board_precision: Literal['FP32','W8A8'] = 'FP32'
    board_streaming: StrictBool = False


@router.get('/ports')
def ports(user: str = Depends(current_user)):
    return manager.ports()


@router.get('/accelerators')
def accelerators(user: str = Depends(current_user)):
    from ecg_accelerator_resources import resources
    return resources()


@router.post('/uploads')
async def upload(file: UploadFile = File(...), user: str = Depends(current_user)):
    try:
        content = await file.read(manager.MAX_UPLOAD + 1)
        return manager.upload(user, file.filename, content)
    finally:
        await file.close()


@router.post('/sessions', status_code=201)
def start(body: Start, user: str = Depends(current_user)):
    callback = None
    if body.analyze_when_complete and body.kind in {'vendor_csv', 'vendor_serial', 'bridge_csv', 'bridge_serial', 'standard500'}:
        def callback(owner, identifier):
            return _submit_analysis(owner, identifier, body.standard_preprocess)
    return manager.start(user, body.model_dump(), on_complete=callback)


@router.get('/sessions')
def history(shared: bool = False, user: str = Depends(current_user)):
    owners = visible_owners(user, shared)
    from app.services.storage import connect
    counts = {}
    with connect() as db:
        for owner in owners:
            for row in db.execute('SELECT payload FROM records WHERE owner_id=?', (owner['id'],)):
                source = json.loads(row['payload']).get('result', {}).get('source_session_id')
                if source:
                    counts[source] = counts.get(source, 0) + 1
    return [dict(row, owner_username=owner['username'], owned=owner['id']==user,
                 analysis_count=counts.get(row['id'], 0))
            for owner in owners for row in manager.history(owner['id'])]


@router.get('/sessions/{identifier}/analyses')
def analyses(identifier: str, user: str = Depends(current_user)):
    owner, _ = visible_session(user, identifier)
    from app.services.storage import connect
    with connect() as db:
        rows = db.execute('SELECT t.id,t.status,t.record_id,i.payload FROM analysis_tasks t JOIN task_inputs i ON i.task_id=t.id WHERE t.owner_id=? ORDER BY t.created_at DESC', (owner['id'],)).fetchall()
    return [{key: row[key] for key in ('id', 'status', 'record_id')} for row in rows
            if (owner['id']==user or row['record_id']) and json.loads(row['payload']).get('source_session_id') == identifier]


def _analyze_legacy(identifier: str, user: str):
    import csv
    from app.services import records
    from app.core.runner import runner
    from app.core.config import settings
    snapshot = manager.snapshot(user, identifier)
    if snapshot['active']:
        raise ValueError('请先停止测量并等待保存完成')
    # 读取完整落盘序列，绝不拿4096点显示缓存冒充完整测量。
    names = snapshot['files']
    name = next((n for n in names if n.endswith('nominal.csv')), None)
    if not name:
        name = next((n for n in ('normalized.csv', 'result/samples.csv', 'samples.csv') if n in names), None)
    if not name:
        name = next((n for n in names if n.endswith('/samples.csv')), None)
    if not name:
        raise ValueError('此记录尚无可分析的标定波形；请导入含ecg_raw的采集CSV')
    header = snapshot['result']['header'] or {}
    nominal = name.endswith('nominal.csv')
    rate = 500 if nominal else header.get('fs') or (500 if snapshot['kind'].startswith('bridge') else None)
    scale = 1 if nominal else 4096 if name == 'normalized.csv' else header.get('scale')
    if not rate or not scale:
        raise ValueError('记录缺少采样率或幅值比例，不能猜测后分析')
    samples = []
    previous = None
    with manager.file(user, identifier, name).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            index = int(row.get('index', row.get('seq', -1)))
            if previous is not None and index != previous + 1:
                raise ValueError('测量序列有缺口，不能按连续波形分析')
            previous = index
            value = row['ecg_nominal_mv'] if nominal else row.get('sample_int16', row.get('raw'))
            samples.append(float(value) / scale)
            if len(samples) > settings.max_samples:
                raise ValueError('测量超过当前离线分析点数上限，请先截取明确时间段再导入')
    if not samples:
        raise ValueError('此记录没有有效采样点')
    signal = dict(samples=samples, sample_rate_hz=rate, unit='mV',
                  source='measurement:' + snapshot['kind'], source_session_id=identifier)
    content = ('value\n' + '\n'.join(map(str, samples)) + '\n').encode()
    task, created = records.submit_analysis(user, signal, raw_content=content)
    if created:
        runner.enqueue(task['id'])
    return task


@router.get('/sessions/{identifier}')
def snapshot(identifier: str, user: str = Depends(current_user)):
    owner, data = visible_session(user, identifier)
    if owner['id'] != user:
        data = dict(data, files=[], diagnostics={}, capture_info={}, analysis=None, info={
            key:value for key,value in data['info'].items() if key in {'state','error','source_samples'}})
    return dict(data, owned=owner['id']==user, owner_username=owner['username'])


@router.post('/sessions/{identifier}/stop')
def stop(identifier: str, user: str = Depends(current_user)):
    return manager.stop(user, identifier)


class AnalyzeSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    standard_preprocess: Literal['hp05', 'raw'] | None = None


@router.post('/sessions/{identifier}/analyze', status_code=202)
def analyze_session(identifier: str, body: AnalyzeSession | None = None, user: str = Depends(current_user)):
    from ai_model.inference.factory import model_setting
    if model_setting('ECG_MODEL_TYPE', 'hgb').strip().lower() != 'hgb':
        return _analyze_legacy(identifier, user)
    return _submit_analysis(user, identifier, body.standard_preprocess if body else None)


def _submit_analysis(user, identifier, standard_preprocess):
    task, created = live_analysis.submit(manager, user, identifier,
                                        standard_preprocess=standard_preprocess)
    if created:
        runner.enqueue(task['id'])
    return task


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
