"""Opt-in ASGI gate BEFORE multipart parsing. Not installed on existing routes."""
import asyncio
from time import monotonic
from starlette.formparsers import MultiPartParser

MAX_BODY=11*1024*1024


class DriverMultipartParser(MultiPartParser):
    # The outer body gate bounds ALL parts together. Keep parsing spools in
    # memory; never spill identity documents into the shared OS temp directory.
    spool_max_size=MAX_BODY+1


class DriverDocumentBodyLimit:
    def __init__(self, app, paths): self.app,self.paths=app,frozenset(paths)

    async def __call__(self, scope, receive, send):
        if scope['type']!='http' or scope['path'] not in self.paths:
            return await self.app(scope,receive,send)
        data=bytearray(); start=monotonic()
        try:
            while True:
                remaining=30-(monotonic()-start)
                if remaining<=0: raise TimeoutError()
                message=await asyncio.wait_for(receive(),timeout=min(5,remaining))
                if message['type']=='http.disconnect': return
                chunk=message.get('body',b'')
                if len(data)+len(chunk)>MAX_BODY:
                    return await self.reject(send,413)
                data.extend(chunk)
                if not message.get('more_body',False): break
        except (TimeoutError,asyncio.TimeoutError):
            return await self.reject(send,408)
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if delivered: return await receive()
            delivered=True
            return dict(type='http.request',body=bytes(data),more_body=False)
        await self.app(scope,bounded_receive,send)

    @staticmethod
    async def reject(send,status):
        await send(dict(type='http.response.start',status=status,headers=[(b'cache-control',b'no-store')]))
        await send(dict(type='http.response.body',body=b'Document request rejected'))
