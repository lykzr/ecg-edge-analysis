"""硬件模块维护设备适配，记录模块维护记录入口。"""
from fastapi import APIRouter, Depends

from app.api.auth import current_user
from app.core.runner import runner
from app.services import records
from hardware.acquisition import sample

router = APIRouter(prefix='/acquisition', tags=['采集接入'])


@router.get('/status')
def status(user: str = Depends(current_user)):
    from app.api.live import manager
    sessions = manager.history(user)
    active = next((row for row in sessions if row['active']), None)
    return {'connected': bool(active), 'mode': active['kind'] if active else 'idle',
            'message': '有实时会话，进入实时与板卡页查看来源及连接状态' if active else '实时会话未开始；进入实时与板卡页选择来源并连接。USB枚举不代表数据已确认。'}


@router.post('/replay', status_code=202)
def replay(user: str = Depends(current_user)):
    task = records.submit(user, sample())
    runner.enqueue(task['id'])
    return task
