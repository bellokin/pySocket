from typing import Callable, List
from ..connectionEngine.connection import WebSocketConnection

async def apply_middleware(connection: WebSocketConnection, path: str, middleware: List[Callable]) -> bool:
    for mw in middleware:
        if not await mw(connection, path):
            return False
    return True