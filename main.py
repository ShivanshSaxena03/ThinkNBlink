from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

clients = []
leaderboard = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("🔥 WebSocket request received")

    await websocket.accept()
    clients.append(websocket)

    print("✅ Connected")

    await websocket.send_json({
        "type": "leaderboard",
        "data": leaderboard
    })

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "new_score":
                leaderboard.append(data["payload"])

                leaderboard.sort(
                    key=lambda x: (-x["level"], -x["score"], x["time"])
                )

                # ✅ SAFE BROADCAST
                disconnected = []
                for client in clients:
                    try:
                        await client.send_json({
                            "type": "leaderboard",
                            "data": leaderboard
                        })
                    except:
                        disconnected.append(client)

                # remove dead clients
                for d in disconnected:
                    clients.remove(d)

    except WebSocketDisconnect:
        if websocket in clients:
            clients.remove(websocket)
        print("❌ Disconnected")