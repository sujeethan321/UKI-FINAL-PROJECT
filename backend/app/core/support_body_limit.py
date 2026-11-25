# Purpose: Bound streamed support POST bodies in memory before endpoint parsing, without disk spooling.
"""64 KiB pre-parse support-body gate, including streamed requests. No disk spools."""
import asyncio

# Apply the support-specific body gate before JSON/schema validation can allocate a larger payload.
class SupportBodyLimit:
    # Initialize the dependencies and state this instance needs for later operations.
    def __init__(self,app):self.app=app
    # Read and bound streamed support bodies before forwarding the buffered request to the application.
    async def __call__(self,scope,receive,send):
        # Scope metadata identifies the endpoint without decoding or trusting the submitted body.
        path=scope.get('path','')
        if scope['type']!='http' or scope.get('method')!='POST' or not path.startswith(('/api/v1/support/cases','/api/v1/admin/support/cases')):
            return await self.app(scope,receive,send)
        # Support descriptions need a larger budget than profile fields, but still stay bounded in memory.
        data=bytearray()
        try:
            # A deadline for the whole stream prevents slow clients from retaining this buffer indefinitely.
            async with asyncio.timeout(15):
                while True:
                    message=await receive()
                    # A disconnected client no longer needs a response or downstream processing.
                    if message['type']=='http.disconnect':return
                    chunk=message.get('body',b'')
                    # Enforce 64 KiB against actual received chunks even if Content-Length is absent or misleading.
                    if len(data)+len(chunk)>65536:return await self.reject(send,413)
                    data.extend(chunk)
                    if not message.get('more_body',False):break
        except TimeoutError:return await self.reject(send,408)
        # Replay the validated bytes once because the downstream app has not yet read its body events.
        delivered=False
        # Deliver the already bounded body once, then delegate any later receive calls to the original ASGI channel.
        async def replay():
            nonlocal delivered
            if delivered:return await receive()
            delivered=True;return {'type':'http.request','body':bytes(data),'more_body':False}
        return await self.app(scope,replay,send)
    # Send the fixed JSON limit error with no-store headers so rejected request details are not cached.
    @staticmethod
    async def reject(send,status):
        await send({'type':'http.response.start','status':status,'headers':[(b'cache-control',b'no-store'),(b'content-type',b'application/json')]})
        await send({'type':'http.response.body','body':b'{"detail":"Support request exceeds size or time limits"}'})
