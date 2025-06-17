import json
import logging
from typing import Dict, Any
from ..serverConfig.socketServer import PySocketServer
from ..routing.router import WebSocketRouter
from ..connectionEngine.connection import WebSocketConnection

logger = logging.getLogger("pysocket.asgi")

class ASGIConnectionWrapper(WebSocketConnection):
    def __init__(self, scope: Dict[str, Any], receive, send):
        super().__init__()
        self.scope = scope
        self._receive = receive
        self._send = send
        self._closed = False
        self.logger = logger
        self.path = scope.get('path', '/')

    async def handshake(self):
        self.logger.debug(f"ASGI handshake for path {self.path}")
        # Handshake handled by ASGI server (Daphne)

    async def receive(self):
        if self._closed:
            self.logger.debug("Receive attempted on closed connection")
            return None
        try:
            message = await self._receive()
            self.logger.debug(f"Received ASGI message: {message}")
            if message['type'] == 'websocket.disconnect':
                self._closed = True
                self.logger.info("Received websocket.disconnect")
                return None
            text = message.get('text')
            if text:
                self.logger.debug(f"Received text: {text}")
                return text
            return None
        except Exception as e:
            self.logger.error(f"Receive error: {e}")
            await self.close()
            return None

    async def send(self, message: str):
        if self._closed:
            self.logger.warning("Attempted to send on closed ASGI connection")
            return
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            await self._send({'type': 'websocket.send', 'text': message})
            self.logger.debug(f"Sent ASGI message: {message}")
        except Exception as e:
            self.logger.error(f"ASGI send error: {e}")
            await self.close()

    async def close(self):
        if not self._closed:
            self._closed = True
            try:
                await self._send({'type': 'websocket.close', 'code': 1000})
                self.logger.info(f"Closed ASGI connection for path {self.path}")
            except Exception as e:
                self.logger.error(f"ASGI close error: {e}")

class ASGIAdapter:
    def __init__(self, server: PySocketServer, router: WebSocketRouter = None):
        self.server = server
        self.router = router or WebSocketRouter()
        self.logger = logger

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'websocket':
            self.logger.warning(f"Non-WebSocket scope: {scope['type']}")
            return

        self.logger.info(f"New WebSocket connection for path {scope.get('path')}")
        message = await receive()
        if message['type'] != 'websocket.connect':
            self.logger.warning(f"Expected websocket.connect, got {message['type']}")
            await send({'type': 'websocket.close', 'code': 1000})
            return

        await send({'type': 'websocket.accept'})
        connection = ASGIConnectionWrapper(scope, receive, send)
        path = scope.get('path', '/')
        consumer = self.router.resolve(path)
        if consumer:
            self.logger.info(f"Resolved consumer {consumer.__name__} for path {path}")
        else:
            self.logger.warning(f"No consumer resolved for path {path}")
        await self.server.handle_connection(connection, path, consumer)