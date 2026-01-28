import threading
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import utils
import crypto
import net
import asyncio

app = FastAPI()

# CORS (front local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- état en mémoire (démo) ---
STATE = {
    "key": utils.gen_key(),
    "messages": [],  # list[str]
    "clients": set(),  # set[WebSocket]
    "loop" : None,
}

def broadcast(event: dict):
    # simple: push to all ws clients
    dead = []
    for ws in list(STATE["clients"]):
        try:
            # FastAPI WS send_json is async; we handle it below via create_task in endpoint.
            # Here we store event and let the ws loop send it.
            pass
        except Exception:
            dead.append(ws)
    for ws in dead:
        STATE["clients"].discard(ws)

# --- modèles API ---
class SendBody(BaseModel):
    peer: str          # "IP:PORT"
    key_b64: str       # shared K (base64)
    message: str

class SetKeyBody(BaseModel):
    key_b64: str

@app.get("/health")
def health():
    return {"ok": True, "p2p_port": config.P2P_PORT}

@app.get("/key")
def get_key():
    return {
        "key_b64": utils.b64e(STATE["key"]),
        "fingerprint": utils.key_fingerprint(STATE["key"]),
    }

@app.post("/key")
def set_key(body: SetKeyBody):
    STATE["key"] = utils.b64d(body.key_b64)
    return {"fingerprint": utils.key_fingerprint(STATE["key"])}

@app.post("/send")
def send_msg(body: SendBody):
    key = utils.b64d(body.key_b64)
    host, port_s = body.peer.split(":")
    port = int(port_s)

    blob = crypto.encrypt(key, body.message)
    frame = {"type": "msg", "blob_b64": utils.b64e(blob)}
    net.send_frame(host, port, frame)

    return {"sent": True}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    STATE["clients"].add(ws)

    if STATE["loop"] is None:
        STATE["loop"] = asyncio.get_running_loop()

    await ws.send_json({"type": "hello", "messages": STATE["messages"]})

    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        STATE["clients"].discard(ws)


async def _broadcast_async(event: dict):
    dead = []
    for ws in list(STATE["clients"]):
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        STATE["clients"].discard(ws)

def broadcast_from_thread(event: dict):
    """
    Appelable depuis le thread TCP (listener).
    Envoie l'event au loop asyncio de FastAPI.
    """
    loop = STATE.get("loop")
    if loop is None:
        return
    asyncio.run_coroutine_threadsafe(_broadcast_async(event), loop)


def start_p2p():
    def on_frame(frame):
        # frame = {"type": "msg", "blob_b64": "..."} envoyé par un autre peer

        if frame.get("type") == "msg":
            blob = utils.b64d(frame["blob_b64"])

            try:
                # Déchiffrement AES-GCM
                msg = crypto.decrypt(STATE["key"], blob)
                STATE["messages"].append(msg)

                # On push au front via WS
                broadcast_from_thread({
                    "type": "message_received",
                    "message": msg
                })

            except Exception as e:
                err = f"[DECRYPT ERROR] {e}"
                STATE["messages"].append(err)
                broadcast_from_thread({
                    "type": "message_received",
                    "message": err
                })

    net.serve(config.P2P_HOST, config.P2P_PORT, on_frame)

if __name__ == "__main__":
    # start TCP listener
    t = threading.Thread(target=start_p2p, daemon=True)
    t.start()

    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)

@app.get("/messages")
def get_messages():
    return {"messages": STATE["messages"]}

