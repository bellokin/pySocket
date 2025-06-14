# pysocket/connection.py
import asyncio
import base64
import hashlib
import re
from typing import Optional, Tuple

# pysocket/connection.py
import asyncio
import base64
import hashlib
import struct
from typing import Optional

class WebSocketConnection:
    MAGIC_STRING = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False
        self._ping_interval = 20  # seconds
        self._ping_timeout = 30  # seconds

    async def handshake(self) -> None:
        """Enhanced WebSocket handshake with proper headers"""
        request = await self._read_http_request()
        headers = self._parse_headers(request)
        
        if 'Sec-WebSocket-Key' not in headers:
            raise ValueError("Missing WebSocket key")
            
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {self._create_accept_key(headers['Sec-WebSocket-Key'])}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.writer.write(response.encode())
        await self.writer.drain()

    def _create_accept_key(self, key: str) -> str:
        return base64.b64encode(
            hashlib.sha1((key + self.MAGIC_STRING).encode()).digest()
        ).decode()

    async def receive(self) -> Optional[str]:
        """Handle WebSocket frames including ping/pong"""
        try:
            while True:
                header = await self.reader.readexactly(2)
                fin = header[0] & 0x80
                opcode = header[0] & 0x0F
                masked = header[1] & 0x80
                payload_len = header[1] & 0x7F

                if payload_len == 126:
                    payload_len = struct.unpack('>H', await self.reader.readexactly(2))[0]
                elif payload_len == 127:
                    payload_len = struct.unpack('>Q', await self.reader.readexactly(8))[0]

                if masked:
                    masking_key = await self.reader.readexactly(4)

                payload = await self.reader.readexactly(payload_len)
                
                if masked:
                    payload = bytes(payload[i] ^ masking_key[i % 4] for i in range(len(payload)))

                # Handle control frames
                if opcode == 0x8:  # Close
                    await self.close()
                    return None
                elif opcode == 0x9:  # Ping
                    await self._send_pong(payload)
                    continue
                elif opcode == 0xA:  # Pong
                    continue
                elif opcode == 0x1:  # Text
                    return payload.decode('utf-8')
                
        except (asyncio.IncompleteReadError, ConnectionError):
            await self.close()
            return None

    async def _send_pong(self, payload: bytes):
        """Respond to ping frames"""
        header = bytearray()
        header.append(0x8A)  # FIN + Pong opcode
        header.append(len(payload))
        self.writer.write(header + payload)
        await self.writer.drain()

    async def send_ping(self):
        """Send ping frame"""
        if not self._closed:
            header = bytearray([0x89, 0x0])  # Ping frame
            self.writer.write(header)
            await self.writer.drain()

    # ... (rest of your existing methods remain the same) ...

    async def handshake(self) -> None:
        """Perform WebSocket handshake"""
        request = await self._read_http_request()
        headers = self._parse_headers(request)
        
        if 'Sec-WebSocket-Key' not in headers:
            raise ValueError("Missing WebSocket key")
            
        response = self._create_handshake_response(headers['Sec-WebSocket-Key'])
        self.writer.write(response.encode())
        await self.writer.drain()

    async def _read_http_request(self) -> str:
        """Read HTTP request from client"""
        request = []
        while True:
            line = await self.reader.readline()
            if line == b'\r\n':
                break
            request.append(line.decode().strip())
        return '\n'.join(request)

    def _parse_headers(self, request: str) -> dict:
        """Parse HTTP headers"""
        headers = {}
        for line in request.split('\n')[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
        return headers

    def _create_handshake_response(self, key: str) -> str:
        """Create WebSocket handshake response"""
        accept_key = base64.b64encode(
            hashlib.sha1((key + self.MAGIC_STRING).encode()).digest()
        ).decode()
        
        return (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )

    async def receive(self) -> Optional[str]:
        """Receive WebSocket message"""
        if self._closed:
            return None
            
        try:
            # Read frame header
            header = await self.reader.readexactly(2)
            fin = (header[0] & 0x80) != 0
            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            payload_length = header[1] & 0x7F
            
            if payload_length == 126:
                payload_length = int.from_bytes(
                    await self.reader.readexactly(2), 'big')
            elif payload_length == 127:
                payload_length = int.from_bytes(
                    await self.reader.readexactly(8), 'big')
                
            if masked:
                masking_key = await self.reader.readexactly(4)
                
            payload = await self.reader.readexactly(payload_length)
            
            if masked:
                payload = bytes(
                    payload[i] ^ masking_key[i % 4]
                    for i in range(len(payload))
                )
                
            if opcode == 0x08:  # Connection close
                await self.close()
                return None
                
            return payload.decode('utf-8')
        except (asyncio.IncompleteReadError, ConnectionError):
            await self.close()
            return None

    async def send(self, message: str) -> None:
        """Send WebSocket message"""
        if self._closed:
            return
            
        header = bytearray()
        payload = message.encode('utf-8')
        payload_length = len(payload)
        
        # Build frame header
        header.append(0x81)  # FIN + Text frame
        
        if payload_length <= 125:
            header.append(payload_length)
        elif payload_length <= 65535:
            header.append(126)
            header.extend(payload_length.to_bytes(2, 'big'))
        else:
            header.append(127)
            header.extend(payload_length.to_bytes(8, 'big'))
            
        self.writer.write(header)
        self.writer.write(payload)
        await self.writer.drain()

    async def close(self) -> None:
        """Close WebSocket connection"""
        if not self._closed:
            self._closed = True
            try:
                self.writer.write(b'\x88\x00')  # Close frame
                await self.writer.drain()
            finally:
                self.writer.close()
                await self.writer.wait_closed()