# pysocket/server.py
import asyncio
import websockets
from collections import defaultdict
import json

class PySocketServer:
    def __init__(self):
        self.clients = set()
        self.rooms = defaultdict(set)
        self.event_handlers = {}

    def on(self, event_name):
        def wrapper(func):
            self.event_handlers[event_name] = func
            return func
        return wrapper
    
    def join_room(self, ws, room):
        self.rooms[room].add(ws)

    def leave_room(self, ws, room):
        self.rooms[room].discard(ws)

    def get_rooms(self, ws):
        return [r for r, clients in self.rooms.items() if ws in clients]
    
    
    async def broadcast(self, event, data):
        """Broadcast to *all* clients in all rooms."""
        message = json.dumps({"event": event, "data": data})
        for ws in self.clients:
            await ws.send(message)

    async def emit(self, event, data, room=None):
        message = json.dumps({"event": event, "data": data})
        targets = self.clients if room is None else self.rooms[room]
        for ws in targets:
            await ws.send(message)

    async def handler(self, websocket, path=None):  # Made path optional
        self.clients.add(websocket)

        if 'connect' in self.event_handlers:
            await self.event_handlers['connect'](websocket, None)

        try:
            async for msg in websocket:
                payload = json.loads(msg)
                event = payload.get("event")
                data = payload.get("data")
                if event in self.event_handlers:
                    await self.event_handlers[event](websocket, data)
        finally:
            self.clients.remove(websocket)
            for r in self.rooms.values():
                r.discard(websocket)

            if 'disconnect' in self.event_handlers:
                await self.event_handlers['disconnect'](websocket, None)

    def run(self, host="localhost", port=8765):
        async def start():
            print(f"pySocket running at ws://{host}:{port}")
            async with websockets.serve(self.handler, host, port):
                await asyncio.Future()  # run forever

        asyncio.run(start())