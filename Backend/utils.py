import base64
import os
import hashlib

def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))

def gen_key() -> bytes:
    # 32 bytes = AES-256 key
    return os.urandom(32)

def key_fingerprint(key: bytes, n: int = 8) -> str:
    h = hashlib.sha256(key).hexdigest()
    return h[:n].upper()
