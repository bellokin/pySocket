import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional, Set
from collections import defaultdict
from functools import wraps
from ..connectionEngine.connection import WebSocketConnection
from ..settings import settings

logger = logging.getLogger("pysocket.server")

class PySocketServer:
    def __init__(self):
        self.clients: Set[WebSocketConnection] = set()
        self.rooms: Dict[str, Set[WebSocketConnection]] = defaultdict(set)
        self.event_handlers: Dict[str, Callable] = {}
        self.logger = logger
        self.middleware = settings.MIDDLEWARE

    def on(self, event_name: str) -> Callable:
        def wrapper(func: Callable) -> Callable:
            @wraps(func)
            async def wrapped(ws: WebSocketConnection, data: Any):
                try:
                    return await func(ws, data)
                except Exception as e:
                    self.logger.error(f"Error in handler {event_name}: {e}")
                    await self.emit("error", {"message": str(e)}, to=ws)
            self.event_handlers[event_name] = wrapped
            return wrapped
        return wrapper

    def join_room(self, connection: WebSocketConnection, room: str) -> None:
        self.rooms[room].add(connection)
        self.logger.info(f"Client {id(connection)} joined room {room}. Room size: {len(self.rooms[room])}")

    def leave_room(self, connection: WebSocketConnection, room: str) -> None:
        self.rooms[room].discard(connection)
        self.logger.info(f"Client {id(connection)} left room {room}. Room size: {len(self.rooms[room])}")

    async def emit(self, event: str, data: Any, room: Optional[str] = None, to: Optional[WebSocketConnection] = None) -> None:
        message = self._format_message(event, data)
        if to:
            targets = [to]
        elif room == "broadcast":
            targets = self.clients
        else:
            targets = self.rooms[room] if room else self.clients
        self.logger.debug(f"Emitting {event} to {len(targets)} targets (room: {room}, to: {to}): {message}")
        for connection in list(targets):
            if not getattr(connection, '_closed', False):
                try:
                    await connection.send(message)
                    self.logger.debug(f"Sent {event} to client {id(connection)}")
                except Exception as e:
                    self.logger.error(f"Failed to send to client {id(connection)}: {e}")
                    await connection.close()
            else:
                self.logger.warning(f"Skipping closed connection {id(connection)}")

    def _format_message(self, event: str, data: Any) -> str:
        return json.dumps({"event": event, "data": data})

    async def handle_connection(self, connection: WebSocketConnection, path: str = None, consumer=None):
        from ..middleware.base import apply_middleware  # Deferred import
        self.logger.info(f"Handling connection {id(connection)} for path {path}")
        if not await apply_middleware(connection, path, self.middleware):
            await connection.close()
            self.logger.warning(f"Middleware rejected connection {id(connection)}")
            return

        self.clients.add(connection)
        connection.path = path
        self.logger.info(f"Added client {id(connection)}. Total clients: {len(self.clients)}")

        if consumer:
            consumer_instance = consumer(connection, self)
            self.logger.info(f"Created consumer instance {consumer.__name__} for {id(connection)}")
            await consumer_instance.connect()

        try:
            while not getattr(connection, '_closed', False):
                message = await asyncio.wait_for(connection.receive(), timeout=settings.PING_INTERVAL)
                if message is None:
                    self.logger.info(f"Connection {id(connection)} closed")
                    break

                try:
                    payload = json.loads(message)
                    event = payload.get("event")
                    data = payload.get("data", {})
                    self.logger.debug(f"Received event {event} from {id(connection)}: {data}")
                    if consumer:
                        await consumer_instance.handle_event(event, data)
                    elif event in self.event_handlers:
                        await self.event_handlers[event](connection, data)
                except json.JSONDecodeError:
                    await connection.send(self._format_message("error", {"message": "Invalid JSON"}))
                    self.logger.warning(f"Invalid JSON from {id(connection)}: {message}")
        except asyncio.TimeoutError:
            self.logger.debug(f"Ping timeout for {id(connection)}")
        except Exception as e:
            self.logger.error(f"Connection error for {id(connection)}: {e}")
        finally:
            await self._cleanup_connection(connection, consumer)

    async def _cleanup_connection(self, connection: WebSocketConnection, consumer=None):
        self.clients.discard(connection)
        for room in list(self.rooms.keys()):
            self.leave_room(connection, room)
        if consumer:
            consumer_instance = consumer(connection, self)
            await consumer_instance.disconnect()
        if "disconnect" in self.event_handlers:
            await self.event_handlers["disconnect"](connection, None)
        self.logger.info(f"Cleaned up connection {id(connection)}. Total clients: {len(self.clients)}")

    async def run(self, host: str = None, port: int = None):
        host = host or settings.HOST
        port = port or settings.PORT
        self.logger.info(f"pySocket running at ws://{host}:{port}")
        server = await asyncio.start_server(self._handle_client, host, port)
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        connection = WebSocketConnection(reader, writer)
        await connection.handshake()
        await self.handle_connection(connection)