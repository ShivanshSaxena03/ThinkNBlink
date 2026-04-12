from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI()

# ✅ CORS (keep open for now)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# 🔥 DATABASE (Render Friendly)
# ==============================

DB_PATH = "/data/leaderboard.db"  # ✅ IMPORTANT for Render disk

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS leaderboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    score INTEGER,
    level INTEGER,
    time INTEGER
)
""")
conn.commit()

# ==============================
# 🔥 GLOBALS
# ==============================

clients = []
leaderboard = []
save_counter = 0


# ==============================
# 🔥 LOAD FROM DB
# ==============================

def load_leaderboard():
    cursor.execute("""
        SELECT name, score, level, time 
        FROM leaderboard
        ORDER BY level DESC, score DESC, time ASC
        LIMIT 100
    """)
    rows = cursor.fetchall()

    return [
        {"name": r[0], "score": r[1], "level": r[2], "time": r[3]}
        for r in rows
    ]


leaderboard = load_leaderboard()


# ==============================
# 🔥 SAVE LAST 5 ENTRIES
# ==============================

def save_last_entries(entries):
    for entry in entries:
        cursor.execute("""
            INSERT INTO leaderboard (name, score, level, time)
            VALUES (?, ?, ?, ?)
        """, (entry["name"], entry["score"], entry["level"], entry["time"]))
    
    conn.commit()
    print("💾 Saved batch to DB")


# ==============================
# 🔥 SAFE BROADCAST FUNCTION
# ==============================

async def broadcast_leaderboard():
    global clients

    disconnected = []

    for client in clients:
        try:
            await client.send_json({
                "type": "leaderboard",
                "data": leaderboard
            })
        except:
            disconnected.append(client)

    # ✅ remove dead clients
    for d in disconnected:
        if d in clients:
            clients.remove(d)


# ==============================
# 🔥 CLEAR ENDPOINT
# ==============================

@app.post("/clear")
async def clear_leaderboard():
    global leaderboard

    leaderboard = []

    cursor.execute("DELETE FROM leaderboard")
    conn.commit()

    await broadcast_leaderboard()

    return {"message": "Leaderboard cleared"}


# ==============================
# 🔥 WEBSOCKET
# ==============================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global clients, save_counter

    await websocket.accept()
    clients.append(websocket)

    print("✅ Client connected. Total:", len(clients))

    # Send initial data
    await websocket.send_json({
        "type": "leaderboard",
        "data": leaderboard
    })

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "new_score":
                payload = data["payload"]

                # ✅ Add to memory
                leaderboard.append(payload)

                # ✅ Sort leaderboard
                leaderboard.sort(
                    key=lambda x: (-x["level"], -x["score"], x["time"])
                )

                # ✅ Limit to top 100 (OPTIMIZATION)
                leaderboard[:] = leaderboard[:100]

                save_counter += 1

                # ✅ Save every 5 scores
                if save_counter >= 5:
                    save_last_entries(leaderboard[:5])  # save top entries
                    save_counter = 0

                # ✅ Broadcast safely
                await broadcast_leaderboard()

    except WebSocketDisconnect:
        if websocket in clients:
            clients.remove(websocket)

        print("❌ Client disconnected. Total:", len(clients))


# ==============================
# 🔥 HEALTH CHECK (IMPORTANT FOR RENDER)
# ==============================

@app.get("/")
def root():
    return {"status": "Server running 🚀"}