# run_server.py

import logging
import asyncio

# Try importing WebSocketConnection to verify if connectionEngine is available
try:
    from pysocket.connectionEngine.connection import WebSocketConnection
    print("[✓] Successfully imported WebSocketConnection from connectionEngine")
except ModuleNotFoundError as e:
    print("[✗] Failed to import connectionEngine.connection:")
    print(f"    {e}")

# Now import your socket server
from pysocket.serverConfig.socketServer import PySocketServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pysocket")

server = PySocketServer()  # Now purely in-memory

# Example middleware
@server.add_middleware
async def auth_middleware(websocket, path):
    """Example authentication middleware"""
    # Implement your auth logic here
    # Return False to reject the connection
    return True

@server.on("connect")
async def on_connect(ws, _):
    logger.info(f"Client connected: {id(ws)}")

@server.on("join")
async def join(ws, data):
    room = data.get("room")
    if not room:
        await server.emit("error", {"message": "Room not specified"}, to=ws)
        return
        
    server.join_room(ws, room)
    await server.emit("joined", {"room": room}, room=room)
    logger.info(f"Client {id(ws)} joined room {room}")

@server.on("message")
async def handle_message(ws, data):
    room = data.get("room")
    msg = data.get("message")
    if not room or not msg:
        await server.emit("error", {"message": "Invalid message format"}, to=ws)
        return
        
    await server.emit("message", {
        "message": msg,
        "sender": str(id(ws)),
        "timestamp": asyncio.get_event_loop().time()
    }, room=room)

@server.on("broadcast")
async def handle_broadcast(ws, data):
    msg = data.get("message")
    if not msg:
        await server.emit("error", {"message": "No message provided"}, to=ws)
        return
        
    await server.broadcast("broadcast", {
        "message": msg,
        "sender": str(id(ws))
    })

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8765)


# # run_server.py
# from pysocket.serverConfig.socketServer import PySocketServer
# import logging
# import asyncio

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("pysocket")

# server = PySocketServer()  # Now purely in-memory

# # Example middleware
# @server.add_middleware
# async def auth_middleware(websocket, path):
#     """Example authentication middleware"""
#     # Implement your auth logic here
#     # Return False to reject the connection
#     return True

# @server.on("connect")
# async def on_connect(ws, _):
#     logger.info(f"Client connected: {id(ws)}")

# @server.on("join")
# async def join(ws, data):
#     room = data.get("room")
#     if not room:
#         await server.emit("error", {"message": "Room not specified"}, to=ws)
#         return
        
#     server.join_room(ws, room)
#     await server.emit("joined", {"room": room}, room=room)
#     logger.info(f"Client {id(ws)} joined room {room}")

# @server.on("message")
# async def handle_message(ws, data):
#     room = data.get("room")
#     msg = data.get("message")
#     if not room or not msg:
#         await server.emit("error", {"message": "Invalid message format"}, to=ws)
#         return
        
#     await server.emit("message", {
#         "message": msg,
#         "sender": str(id(ws)),
#         "timestamp": asyncio.get_event_loop().time()
#     }, room=room)

# @server.on("broadcast")
# async def handle_broadcast(ws, data):
#     msg = data.get("message")
#     if not msg:
#         await server.emit("error", {"message": "No message provided"}, to=ws)
#         return
        
#     await server.broadcast("broadcast", {
#         "message": msg,
#         "sender": str(id(ws))
#     })

# if __name__ == "__main__":
#     server.run(host="0.0.0.0", port=8765)