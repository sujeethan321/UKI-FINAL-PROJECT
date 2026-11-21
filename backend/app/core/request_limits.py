"""Bound incoming bodies before form/JSON parsing, including chunked requests."""
from fastapi.responses import JSONResponse


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_bytes=262144):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        maximum = 11*1024*1024 if scope['method']=='POST' and scope['path'].rstrip('/')=='/api/v1/driver/vehicle' else self.max_bytes
        try:
            length = int(headers.get(b'content-length', b'0'))
            if length < 0:
                raise ValueError
        except ValueError:
            return await JSONResponse({'detail': 'Invalid request length'}, status_code=400)(scope, receive, send)
        if length > maximum:
            return await JSONResponse({'detail': 'Request body too large'}, status_code=413)(scope, receive, send)
        if scope['method']=='POST' and scope['path'].rstrip('/')=='/api/v1/driver/vehicle':
            from app.core.driver_document_body_limit import DriverDocumentBodyLimit
            return await DriverDocumentBodyLimit(self.app,{scope['path']})(scope,receive,send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body) + len(chunk) > maximum:
                return await JSONResponse({'detail': 'Request body too large'}, status_code=413)(scope, receive, send)
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        return await self.app(scope, replay, send)
