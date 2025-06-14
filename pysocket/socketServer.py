# pysocket/server.py
import asyncio
import websockets
from collections import defaultdict
import json
from functools import wraps
import logging

class PySocketServer:
    def __init__(self):
        self.clients = set()
        self.rooms = defaultdict(set)
        self.event_handlers = {}
        self.logger = logging.getLogger("pysocket")
        
        # Middleware support
        self.middleware = []
        
    def add_middleware(self, middleware):
        """Add middleware for connection handling"""
        self.middleware.append(middleware)
        
    async def apply_middleware(self, websocket, path):
        """Apply all middleware to the connection"""
        for middleware in self.middleware:
            if not await middleware(websocket, path):
                return False
        return True

    def on(self, event_name):
        def wrapper(func):
            @wraps(func)
            async def wrapped(ws, data):
                try:
                    return await func(ws, data)
                except Exception as e:
                    self.logger.error(f"Error in handler {event_name}: {e}")
                    await self.emit("error", {"message": str(e)}, to=ws)
            self.event_handlers[event_name] = wrapped
            return wrapped
        return wrapper
    
    def join_room(self, ws, room):
        """Join a room"""
        self.rooms[room].add(ws)

    def leave_room(self, ws, room):
        """Leave a room"""
        self.rooms[room].discard(ws)

    def get_rooms(self, ws):
        return [r for r, clients in self.rooms.items() if ws in clients]
    
    async def broadcast(self, event, data):
        """Broadcast to all connected clients"""
        message_str = json.dumps({"event": event, "data": data})
        for ws in self.clients:
            await ws.send(message_str)

    async def emit(self, event, data, room=None, to=None):
        """
        Send message to specific targets:
        - room: send to all in room
        - to: send to specific client(s)
        - neither: send to all clients
        """
        message_str = json.dumps({"event": event, "data": data})
        
        if to:
            targets = [to] if not isinstance(to, (list, set)) else to
        elif room:
            targets = self.rooms[room]
        else:
            targets = self.clients
            
        for ws in targets:
            await ws.send(message_str)

    async def handler(self, websocket, path=None):
        """Main WebSocket handler with middleware support"""
        if not await self.apply_middleware(websocket, path):
            return
            
        self.clients.add(websocket)
        
        if 'connect' in self.event_handlers:
            await self.event_handlers['connect'](websocket, None)

        try:
            async for msg in websocket:
                try:
                    payload = json.loads(msg)
                    event = payload.get("event")
                    data = payload.get("data")
                    if event in self.event_handlers:
                        await self.event_handlers[event](websocket, data)
                except json.JSONDecodeError:
                    await self.emit("error", {"message": "Invalid JSON"}, to=websocket)
        finally:
            self.clients.discard(websocket)
            for room in list(self.rooms.keys()):
                self.leave_room(websocket, room)

            if 'disconnect' in self.event_handlers:
                await self.event_handlers['disconnect'](websocket, None)

    def run(self, host="localhost", port=8765):
        """Run the server with enhanced options"""
        async def start():
            self.logger.info(f"pySocket running at ws://{host}:{port}")
                
            async with websockets.serve(
                self.handler,
                host,
                port,
                ping_interval=20,
                ping_timeout=60,
                close_timeout=10
            ):
                await asyncio.Future()  # run forever

        asyncio.run(start())