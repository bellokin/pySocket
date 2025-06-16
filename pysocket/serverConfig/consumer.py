import logging
from typing import Any
from ..serverConfig.socketServer import PySocketServer
from ..connectionEngine.connection import WebSocketConnection

logger = logging.getLogger("pysocket.consumer")

class WebSocketConsumer:
    def __init__(self, connection: WebSocketConnection, server: PySocketServer):
        self.connection = connection
        self.server = server
        self.logger = logger

    async def connect(self):
        self.logger.debug(f"Consumer connected for {id(self.connection)}")

    async def disconnect(self):
        self.logger.debug(f"Consumer disconnected for {id(self.connection)}")

    async def handle_event(self, event: str, data: Any):
        handler = getattr(self, f"handle_{event}", None)
        if handler:
            self.logger.debug(f"Handling event {event} with data {data}")
            await handler(data)
        else:
            self.logger.warning(f"No handler for event {event}")
            await self.server.emit("error", {
                "message": f"Unknown event: {event}"
            }, to=self.connection)

    async def handle_message(self, data):
        self.logger.info(f"Default handle_message received: {data}")
        await self.server.emit("echo", data, to=self.connection)