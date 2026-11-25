# Purpose: Bound personal-profile PATCH bodies by both size and time before FastAPI parses the JSON.
"""Small pre-parse bound for the two-field personal-profile PATCH."""
# asyncio.timeout bounds the whole body read, including time spent waiting for a slow client.
import asyncio

# Wrap the downstream ASGI application so the profile size limit runs before JSON/schema parsing.
class ProfileBodyLimit:
    # Keep the next ASGI application so accepted requests can continue through the normal middleware stack.
    def __init__(self,app):self.app=app
    # ASGI supplies request metadata in scope, incoming body events through receive, and response output through send.
    async def __call__(self,scope,receive,send):
        # Limit only the personal-profile PATCH; websocket traffic and other endpoints retain their own policies.
        if scope['type']!='http' or scope.get('method')!='PATCH' or scope.get('path','').rstrip('/')!='/api/v1/account/profile':
            return await self.app(scope,receive,send)
        # Accumulate a bounded body in memory; bytearray avoids copying the entire buffer for every chunk.
        data=bytearray()
        try:
            # One 15-second deadline covers every chunk, so repeatedly sending tiny chunks cannot reset the allowance.
            async with asyncio.timeout(15):
                while True:
                    # ASGI bodies may arrive in multiple events even when the request contains one JSON object.
                    message=await receive()
                    # Stop quietly if the client is gone rather than attempting to process or respond to its request.
                    if message['type']=='http.disconnect':return
                    chunk=message.get('body',b'')
                    # Count received bytes, not a claimed Content-Length, and reject before extending beyond 4 KiB.
                    if len(data)+len(chunk)>4096:return await self.reject(send,413)
                    data.extend(chunk)
                    # The final body event ends accumulation and makes the bounded payload ready for downstream parsing.
                    if not message.get('more_body',False):break
        # Distinguish an overlong body read (408) from an oversized body (413).
        except TimeoutError:return await self.reject(send,408)
        # The downstream app must receive the buffered body once because this middleware has already consumed it.
        delivered=False
        # Deliver the already bounded body once, then delegate any later receive calls to the original ASGI channel.
        async def replay():
            # Share the delivery marker with the surrounding request scope rather than creating a new local flag.
            nonlocal delivered
            if delivered:return await receive()
            delivered=True;return {'type':'http.request','body':bytes(data),'more_body':False}
        # Substitute only receive; preserve the original request metadata and response channel.
        return await self.app(scope,replay,send)
    # Send a fixed JSON error without caching it or exposing internal parser details; no instance state is needed.
    @staticmethod
    async def reject(send,status):
        # ASGI sends response status/headers before the response body and represents header names and values as bytes.
        await send({'type':'http.response.start','status':status,'headers':[(b'cache-control',b'no-store'),(b'content-type',b'application/json')]})
        await send({'type':'http.response.body','body':b'{"detail":"Profile request exceeds size or time limits"}'})
