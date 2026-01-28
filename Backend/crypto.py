from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

def encrypt(key: bytes, plaintext: str) -> bytes:
    aes = AESGCM(key)
    nonce = os.urandom(12)  # GCM nonce = 12 bytes
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct  # pack: nonce||ciphertext+tag

def decrypt(key: bytes, blob: bytes) -> str:
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    pt = aes.decrypt(nonce, ct, None)
    return pt.decode("utf-8")
