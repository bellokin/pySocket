# run_server.py
from pysocket.socketServer import PySocketServer

server = PySocketServer()

@server.on("connct")
async def on_connect(ws, _):
    print("Client connected")

@server.on("join")
async def join(ws, data):
    room = data.get("room")
    server.join_room(ws, room)
    await server.emit("joined", {"room": room}, room=room)

@server.on("message")
async def handle_message(ws, data):
    room = data.get("room")
    msg = data.get("message")
    await server.emit("message", {"message": msg}, room=room)

@server.on("broadcast")
async def handle_broadcast(ws, data):
    msg = data.get("message")
    await server.broadcast("broadcast", {"message": msg})

server.run()
