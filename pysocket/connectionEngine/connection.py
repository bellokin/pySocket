import asyncio
import logging
from typing import Optional

logger = logging.getLogger("pysocket.connection")

class WebSocketConnection:
    def __init__(self, reader: Optional[asyncio.StreamReader] = None, writer: Optional[asyncio.StreamWriter] = None):
        self.reader = reader
        self.writer = writer
        self.path = None
        self._closed = False
        self.logger = logger

    async def handshake(self):
        self.logger.debug(f"Performing WebSocket handshake for path {self.path}")
        if self.reader and self.writer:
            try:
                request = await self.reader.readuntil(b'\r\n\r\n')
                self.logger.debug(f"Received handshake request: {request.decode('utf-8')}")
                response = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    "Sec-WebSocket-Accept: dummy\r\n"
                    "\r\n"
                )
                self.writer.write(response.encode('utf-8'))
                await self.writer.drain()
                self.logger.info("Handshake completed")
            except Exception as e:
                self.logger.error(f"Handshake error: {e}")
                await self.close()

    async def send(self, message: str):
        if self._closed:
            self.logger.warning("Attempted to send on closed connection")
            return
        try:
            if self.writer:
                self.writer.write((message + '\n').encode('utf-8'))
                await self.writer.drain()
                self.logger.debug(f"Sent message: {message}")
        except Exception as e:
            self.logger.error(f"Send error: {e}")
            await self.close()

    async def receive(self) -> Optional[str]:
        if self._closed:
            self.logger.debug("Receive attempted on closed connection")
            return None
        try:
            if self.reader:
                data = await self.reader.readline()
                if not data:
                    await self.close()
                    return None
                message = data.decode('utf-8').strip()
                self.logger.debug(f"Received message: {message}")
                return message
        except Exception as e:
            self.logger.error(f"Receive error: {e}")
            await self.close()
            return None

    async def close(self):
        if not self._closed:
            self._closed = True
            if self.writer:
                try:
                    self.writer.close()
                    await self.writer.wait_closed()
                    self.logger.info(f"Closed connection for path {self.path}")
                except Exception as e:
                    self.logger.error(f"Close error: {e}")