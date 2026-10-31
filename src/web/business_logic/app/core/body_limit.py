"""在multipart解析前限制实际请求字节，分块上传也不绕过上限。"""
from fastapi.responses import JSONResponse


class BodyTooLarge(Exception):
    pass


class BodyLimit:
    def __init__(self, app, maximum=34*1024*1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        total = 0
        started = False

        async def bounded_receive():
            nonlocal total
            message = await receive()
            if message['type'] == 'http.request':
                total += len(message.get('body', b''))
                if total > self.maximum:
                    raise BodyTooLarge()
            return message

        async def tracked_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        except BodyTooLarge:
            if started:
                raise
            await JSONResponse({'detail':'请求数据超过上限','code':'payload_too_large'},status_code=413)(scope,receive,send)
