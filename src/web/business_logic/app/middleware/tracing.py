"""
链路追踪中间件
"""

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class TracingMiddleware(BaseHTTPMiddleware):
    """链路追踪中间件"""

    async def dispatch(self, request: Request, call_next):
        # 生成或提取 trace_id
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))

        # 存储到 request state
        request.state.trace_id = trace_id

        # 处理请求
        response = await call_next(request)

        # 添加 trace header 到响应
        response.headers["X-Trace-ID"] = trace_id

        return response
