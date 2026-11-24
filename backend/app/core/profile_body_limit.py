"""Small pre-parse bound for the two-field personal-profile PATCH."""
import asyncio

class ProfileBodyLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method')!='PATCH' or scope.get('path','').rstrip('/')!='/api/v1/account/profile':
            return await self.app(scope,receive,send)
        data=bytearray()
        try:
            async with asyncio.timeout(15):
                while True:
                    message=await receive()
                    if message['type']=='http.disconnect':return
                    chunk=message.get('body',b'')
                    if len(data)+len(chunk)>4096:return await self.reject(send,413)
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
        await send({'type':'http.response.body','body':b'{"detail":"Profile request exceeds size or time limits"}'})
