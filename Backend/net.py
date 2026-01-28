import json
import socket
import struct
from typing import Callable, Dict, Any

def _recv_exact(conn: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed")
        data += chunk
    return data

def send_frame(host: str, port: int, frame: Dict[str, Any]) -> None:
    raw = json.dumps(frame).encode("utf-8")
    header = struct.pack(">I", len(raw))
    with socket.create_connection((host, port), timeout=5) as s:
        s.sendall(header + raw)

def serve(host: str, port: int, on_frame: Callable[[Dict[str, Any]], None]) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(50)
    while True:
        conn, _ = srv.accept()
        with conn:
            header = _recv_exact(conn, 4)
            (ln,) = struct.unpack(">I", header)
            raw = _recv_exact(conn, ln)
            frame = json.loads(raw.decode("utf-8"))
            on_frame(frame)
