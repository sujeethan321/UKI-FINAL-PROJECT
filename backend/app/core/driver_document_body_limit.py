# Purpose: Constrain driver-document multipart uploads while the request body is being parsed.
"""Opt-in ASGI gate BEFORE multipart parsing. Not installed on existing routes."""
import asyncio
from time import monotonic
from starlette.formparsers import MultiPartParser

MAX_BODY=11*1024*1024


# Group the state and operations for driver multipart parser in the driver document body limit module.
class DriverMultipartParser(MultiPartParser):
    # The outer body gate bounds ALL parts together. Keep parsing spools in
    # memory; never spill identity documents into the shared OS temp directory.
    spool_max_size=MAX_BODY+1


# Group the state and operations for driver document body limit in the driver document body limit module.
class DriverDocumentBodyLimit:
    # Initialize the dependencies and state this instance needs for later operations.
    def __init__(self, app, paths): self.app,self.paths=app,frozenset(paths)

    # Run the configured adapter operation with the input checks and error handling defined by this class.
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
        # Count incoming bytes while reading the request and stop bodies that exceed the configured limit.
        async def bounded_receive():
            nonlocal delivered
            if delivered: return await receive()
            delivered=True
            return dict(type='http.request',body=bytes(data),more_body=False)
        await self.app(scope,bounded_receive,send)

    # Send a fixed no-store document-request rejection without exposing parser internals.
    @staticmethod
    async def reject(send,status):
        await send(dict(type='http.response.start',status=status,headers=[(b'cache-control',b'no-store')]))
        await send(dict(type='http.response.body',body=b'Document request rejected'))
