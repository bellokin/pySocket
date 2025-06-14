# pysocket/asgi.py
from typing import Callable, Dict, Any,Optional
from .connectionEngine.connection import WebSocketConnection

class ASGIAdapter:
    def __init__(self, server):
        self.server = server

    async def __call__(self, scope: Dict, receive: Callable, send: Callable) -> None:
        """ASGI 3.0 interface implementation"""
        if scope['type'] != 'websocket':
            raise ValueError("Only WebSocket connections are supported")
            
        connection = ASGIConnection(scope, receive, send)
        await self.server.handle_connection(connection, scope.get('path'))

class ASGIConnection(WebSocketConnection):
    """Adapter for ASGI WebSocket connection"""
    def __init__(self, scope: Dict, receive: Callable, send: Callable):
        self.scope = scope
        self._receive = receive
        self._send = send
        self._closed = False

    async def receive(self) -> Optional[str]:
        """Receive WebSocket message"""
        if self._closed:
            return None
            
        message = await self._receive()
        if message['type'] == 'websocket.disconnect':
            self._closed = True
            return None
            
        return message.get('text')

    async def send(self, message: str) -> None:
        """Send WebSocket message"""
        if self._closed:
            return
            
        await self._send({
            'type': 'websocket.send',
            'text': message
        })

    async def close(self) -> None:
        """Close WebSocket connection"""
        if not self._closed:
            self._closed = True
            await self._send({'type': 'websocket.close'})