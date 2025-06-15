import asyncio
import json
import logging
import re
import time
from collections import defaultdict
from functools import wraps
from typing import Callable, Optional, Set, Dict, Any
from ..connectionEngine.connection import WebSocketConnection

class PySocketServer:
    def __init__(self):
        self.clients: Set['WebSocketConnection'] = set()
        self.rooms: Dict[str, Set['WebSocketConnection']] = defaultdict(set)
        self.event_handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger("pysocket")
        self.middleware: list = []
        
        # Register event handlers
        self.on("connect")(self.handle_connect)
        self.on("join")(self.handle_join)
        self.on("leave")(self.handle_leave)
        self.on("message")(self.handle_message)
        self.on("broadcast")(self.handle_broadcast)
        self.on("disconnect")(self.handle_disconnect)

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware for connection handling"""
        self.middleware.append(middleware)
        
    async def apply_middleware(self, connection: 'WebSocketConnection', path: str) -> bool:
        """Apply all middleware to the connection"""
        for middleware in self.middleware:
            if not await middleware(connection, path):
                return False
        return True

    def on(self, event_name: str) -> Callable:
        def wrapper(func: Callable) -> Callable:
            @wraps(func)
            async def wrapped(ws: 'WebSocketConnection', data: Any):
                try:
                    return await func(ws, data)
                except Exception as e:
                    self.logger.error(f"Error in handler {event_name}: {e}")
                    await self.emit("error", {"message": str(e)}, to=ws)
            self.event_handlers[event_name] = wrapped
            return wrapped
        return wrapper
    
    def join_room(self, connection: 'WebSocketConnection', room: str) -> None:
        """Join a room"""
        self.rooms[room].add(connection)
        self.logger.info(f"Client {id(connection)} joined room {room}")

    def leave_room(self, connection: 'WebSocketConnection', room: str) -> None:
        """Leave a room"""
        self.rooms[room].discard(connection)
        self.logger.info(f"Client {id(connection)} left room {room}")

    def get_rooms(self, connection: 'WebSocketConnection') -> list:
        """Get all rooms for a connection"""
        return [room for room, connections in self.rooms.items() if connection in connections]
    
    async def broadcast(self, event: str, data: Any) -> None:
        """Broadcast to all connected clients"""
        message = self._format_message(event, data)
        for connection in self.clients:
            await connection.send(message)

    async def emit(self, event: str, data: Any, room: Optional[str] = None, 
                   to: Optional['WebSocketConnection'] = None) -> None:
        """
        Send message to specific targets:
        - room: send to all in room
        - to: send to specific client(s)
        - neither: send to all clients
        """
        message = self._format_message(event, data)
        
        if to:
            targets = [to] if not isinstance(to, (list, set)) else to
        elif room:
            targets = self.rooms[room]
        else:
            targets = self.clients
            
        for connection in targets:
            await connection.send(message)

    def _format_message(self, event: str, data: Any) -> str:
        """Format message as JSON string"""
        return json.dumps({"event": event, "data": data})

    async def handle_connect(self, ws: 'WebSocketConnection', data: Any):
        """Handle client connection"""
        self.logger.info(f"Client connected: {id(ws)}")
        await self.emit("connected", {"message": "Connected to server"}, to=ws)

    async def handle_join(self, ws: 'WebSocketConnection', data: Any):
        """Handle join room event"""
        room = data.get("room")
        if room:
            self.join_room(ws, room)
            await self.emit("room_joined", {
                "room": room,
                "message": f"Joined room {room}"
            }, to=ws)
        else:
            await self.emit("error", {"message": "Room name required"}, to=ws)

    async def handle_leave(self, ws: 'WebSocketConnection', data: Any):
        """Handle leave room event"""
        room = data.get("room")
        if room:
            self.leave_room(ws, room)
            await self.emit("room_left", {
                "room": room,
                "message": f"Left room {room}"
            }, to=ws)
        else:
            await self.emit("error", {"message": "Room name required"}, to=ws)

    async def handle_message(self, ws: 'WebSocketConnection', data: Any):
        """Handle message event"""
        room = data.get("room")
        message = data.get("text")
        if room and message:
            await self.emit("new_message", {
                "from": str(id(ws)),  # Use object ID as unique identifier
                "room": room,
                "text": message,
                "timestamp": int(time.time())
            }, room=room)
        else:
            await self.emit("error", {"message": "Room and message required"}, to=ws)

    async def handle_broadcast(self, ws: 'WebSocketConnection', data: Any):
        """Handle broadcast event"""
        message = data.get("text")
        if message:
            await self.broadcast("broadcast_message", {
                "from": str(id(ws)),  # Use object ID as unique identifier
                "text": message,
                "timestamp": int(time.time())
            })
        else:
            await self.emit("error", {"message": "Broadcast message required"}, to=ws)

    async def handle_disconnect(self, ws: 'WebSocketConnection', data: Any):
        """Handle client disconnection"""
        self.logger.info(f"Client disconnected: {id(ws)}")

    async def handle_connection(self, connection: 'WebSocketConnection', path: str = None):
        """Universal connection handler with room support"""
        # Extract room_name from path
        room_name = None
        if path:
            match = re.match(r'^/ws/chat/(\w+)/$', path)
            if match:
                room_name = match.group(1)

        # Store connection metadata
        connection.path = path
        connection.room = room_name

        if not await self.apply_middleware(connection, path):
            return

        # Add client to set
        self.clients.add(connection)

        # Join room if specified
        if room_name:
            self.join_room(connection, room_name)
            await self.emit("room_joined", {
                "room": room_name,
                "message": f"Auto-joined room {room_name}"
            }, to=connection)

        # Notify connection
        if 'connect' in self.event_handlers:
            await self.event_handlers['connect'](connection, None)

        try:
            last_active = asyncio.get_event_loop().time()
            while not getattr(connection, '_closed', False):
                try:
                    # Handle message receiving
                    timeout = getattr(connection, '_ping_interval', 20)
                    message = await asyncio.wait_for(connection.receive(), timeout=timeout)

                    if message is None:  # Connection closed
                        break

                    try:
                        payload = json.loads(message)
                        event = payload.get("event")
                        data = payload.get("data")

                        # Add room to message data if not present
                        if room_name and isinstance(data, dict) and 'room' not in data:
                            data['room'] = room_name

                        if event in self.event_handlers:
                            await self.event_handlers[event](connection, data)

                        last_active = asyncio.get_event_loop().time()
                    except json.JSONDecodeError:
                        await connection.send(json.dumps({
                            "event": "error",
                            "data": {"message": "Invalid JSON"}
                        }))

                    # Ping if supported
                    if hasattr(connection, 'send_ping'):
                        await connection.send_ping()

                except asyncio.TimeoutError:
                    if asyncio.get_event_loop().time() - last_active > 60:
                        break
                    continue

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")

        finally:
            await self._cleanup_connection(connection)

    async def _cleanup_connection(self, connection: 'WebSocketConnection'):
        """Clean up connection resources"""
        self.clients.discard(connection)
        for room in list(self.rooms.keys()):
            self.leave_room(connection, room)
        if 'disconnect' in self.event_handlers:
            asyncio.create_task(self.event_handlers['disconnect'](connection, None))

    def run(self, host: str = "localhost", port: int = 8765) -> None:
        """Run the server with enhanced options"""
        async def start_server():
            self.logger.info(f"pySocket running at ws://{host}:{port}")
            server = await asyncio.start_server(
                self._handle_client,
                host,
                port
            )
            async with server:
                await server.serve_forever()

        asyncio.run(start_server())

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle new TCP connection and upgrade to WebSocket"""
        connection = WebSocketConnection(reader, writer)
        try:
            await connection.handshake()
            await self.handle_connection(connection)
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
        finally:
            await connection.close()

    def as_asgi(self):
        """Return an ASGI application for Django integration"""
        from pysocket.asgi import ASGIAdapter
        return ASGIAdapter(self)