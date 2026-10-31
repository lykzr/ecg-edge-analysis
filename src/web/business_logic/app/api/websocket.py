"""来源项目实时路径兼容入口；不返回假设备数据。"""
from fastapi import APIRouter, WebSocket
from app.api.live import stream
router = APIRouter()

@router.websocket('/ws/realtime')
async def websocket_endpoint(socket: WebSocket, session_id: str = ''):
    await stream(socket, session_id)
