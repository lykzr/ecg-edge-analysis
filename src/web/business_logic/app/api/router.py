from app.api import auth, family, analyze, acquisition, websocket, system, live
from fastapi import APIRouter

router = APIRouter(prefix='/api/v1')
for module in (auth, family, analyze, acquisition, websocket, system, live):
    router.include_router(module.router)
