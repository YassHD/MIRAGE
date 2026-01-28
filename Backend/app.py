"""
Mirage - Serveur FastAPI
Gère la messagerie chiffrée peer-to-peer
"""

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import uvicorn
from typing import Optional, List

import config
import crypto
import net
import utils

# === FastAPI ===
app = FastAPI(title="Mirage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Modèles ===
class EncryptRequest(BaseModel):
    key: str  # Hex
    message: str

class DecryptRequest(BaseModel):
    key: str  # Hex
    ciphertext: str  # Base64

class SendRequest(BaseModel):
    peer_ip: str
    peer_port: int
    key: str
    message: str


# === État global ===
class State:
    def __init__(self):
        self.current_key: Optional[bytes] = None
        self.websockets: List[WebSocket] = []

state = State()


# === Routes ===

@app.get("/")
async def root():
    return {"app": "Mirage", "status": "running"}


@app.post("/key/generate")
async def generate_key():
    """Génère une clé AES-256"""
    key = utils.gen_key()
    key_hex = key.hex()
    fingerprint = utils.key_fingerprint(key)
    
    state.current_key = key
    
    return {
        "key": key_hex,
        "fingerprint": fingerprint
    }


@app.post("/key/fingerprint")
async def fingerprint(key_hex: str):
    """Calcule le fingerprint d'une clé"""
    key = bytes.fromhex(key_hex)
    return {"fingerprint": utils.key_fingerprint(key)}


@app.post("/encrypt")
async def encrypt(req: EncryptRequest):
    """Chiffre un message"""
    try:
        key = bytes.fromhex(req.key)
        ciphertext = crypto.encrypt(key, req.message)
        return {"ciphertext": utils.b64e(ciphertext)}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/decrypt")
async def decrypt(req: DecryptRequest):
    """Déchiffre un message"""
    try:
        key = bytes.fromhex(req.key)
        ciphertext = utils.b64d(req.ciphertext)
        plaintext = crypto.decrypt(key, ciphertext)
        return {"plaintext": plaintext}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/send")
async def send_message(req: SendRequest):
    """Envoie un message chiffré à un peer"""
    try:
        # Chiffre le message
        key = bytes.fromhex(req.key)
        ciphertext = crypto.encrypt(key, req.message)
        
        # Envoie via TCP
        success = await net.send_tcp_message(
            req.peer_ip,
            req.peer_port,
            ciphertext
        )
        
        if success:
            return {"success": True, "peer": f"{req.peer_ip}:{req.peer_port}"}
        else:
            raise HTTPException(500, "Échec de l'envoi")
            
    except Exception as e:
        raise HTTPException(400, str(e))


# === WebSocket ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket pour les messages en temps réel"""
    await websocket.accept()
    state.websockets.append(websocket)
    
    try:
        while True:
            await websocket.receive_text()
    except:
        state.websockets.remove(websocket)


async def broadcast(message: dict):
    """Envoie un message à tous les clients WebSocket"""
    for ws in state.websockets:
        try:
            await ws.send_json(message)
        except:
            pass


# === Démarrage ===

@app.on_event("startup")
async def startup():
    """Démarre le serveur TCP"""
    print(f"🚀 Mirage sur http://{config.API_HOST}:{config.API_PORT}")
    print(f"📡 P2P sur {config.P2P_HOST}:{config.P2P_PORT}")
    
    # Lance le listener TCP
    asyncio.create_task(start_tcp())


async def start_tcp():
    """Démarre le listener TCP"""
    await net.start_listener(
        config.P2P_HOST,
        config.P2P_PORT,
        on_message_received
    )


async def on_message_received(ciphertext: bytes, peer_addr: tuple):
    """Callback quand un message est reçu"""
    try:
        if state.current_key:
            plaintext = crypto.decrypt(state.current_key, ciphertext)
            
            # Broadcast aux clients WebSocket
            await broadcast({
                "type": "message",
                "from": f"{peer_addr[0]}:{peer_addr[1]}",
                "content": plaintext
            })
            print(f"📨 Message de {peer_addr[0]}: {plaintext[:50]}...")
        else:
            print("⚠️  Message reçu mais pas de clé définie")
    except Exception as e:
        print(f"❌ Erreur déchiffrement: {e}")


# === Main ===

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True
    )