"""64 KiB pre-parse support-body gate, including streamed requests. No disk spools."""
import asyncio

class SupportBodyLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        if scope['type']!='http' or scope.get('method')!='POST' or not path.startswith(('/api/v1/support/cases','/api/v1/admin/support/cases')):
            return await self.app(scope,receive,send)
        data=bytearray()
        try:
            async with asyncio.timeout(15):
                while True:
                    message=await receive()
                    if message['type']=='http.disconnect':return
                    chunk=message.get('body',b'')
                    if len(data)+len(chunk)>65536:return await self.reject(send,413)
                    data.extend(chunk)
                    if not message.get('more_body',False):break
        except TimeoutError:return await self.reject(send,408)
        delivered=False
        async def replay():
            nonlocal delivered
            if delivered:return await receive()
            delivered=True;return {'type':'http.request','body':bytes(data),'more_body':False}
        return await self.app(scope,replay,send)
    @staticmethod
    async def reject(send,status):
        await send({'type':'http.response.start','status':status,'headers':[(b'cache-control',b'no-store'),(b'content-type',b'application/json')]})
        await send({'type':'http.response.body','body':b'{"detail":"Support request exceeds size or time limits"}'})
