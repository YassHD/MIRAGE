import React, { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8765";
const WS_URL = "ws://127.0.0.1:8765/ws";

export default function App() {
  const [keyB64, setKeyB64] = useState("");
  const [fp, setFp] = useState("");
  const [peer, setPeer] = useState("127.0.0.1:4040");
  const [msg, setMsg] = useState("");
  const [messages, setMessages] = useState([]);
  const [wsStatus, setWsStatus] = useState("disconnected");

  const wsRef = useRef(null);
  const pingRef = useRef(null);
  const reconnectRef = useRef(null);

  async function loadKey() {
    const r = await fetch(`${API}/key`);
    const j = await r.json();
    setKeyB64(j.key_b64);
    setFp(j.fingerprint);
  }

  async function send() {
    if (!msg.trim()) return;

    await fetch(`${API}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        peer,
        key_b64: keyB64,
        message: msg,
      }),
    });

    setMsg("");
  }

  function connectWS() {
    // cleanup
    if (reconnectRef.current) clearTimeout(reconnectRef.current);
    if (pingRef.current) clearInterval(pingRef.current);
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {}
    }

    setWsStatus("connecting");
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus("connected");

      // keepalive
      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 20000);
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);

        if (data.type === "hello") {
          setMessages(data.messages || []);
        } else if (data.type === "message_received") {
          setMessages((prev) => [...prev, data.message]);
        }
      } catch {}
    };

    ws.onerror = () => {
      setWsStatus("error");
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      if (pingRef.current) clearInterval(pingRef.current);

      // auto-reconnect
      reconnectRef.current = setTimeout(() => {
        connectWS();
      }, 1000);
    };
  }

  useEffect(() => {
    loadKey();
    connectWS();

    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (pingRef.current) clearInterval(pingRef.current);
      if (wsRef.current) wsRef.current.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ fontFamily: "sans-serif", padding: 16, maxWidth: 900 }}>
      <h2>MIRAGE Mini (Symmetric Demo)</h2>

      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ flex: 1 }}>
          <div>
            <b>Key (base64)</b>
          </div>
          <input
            value={keyB64}
            onChange={(e) => setKeyB64(e.target.value)}
            style={{ width: "100%" }}
          />
          <div style={{ marginTop: 6 }}>
            Fingerprint: <b>{fp}</b>
            {"  "}·{"  "}
            WS: <b>{wsStatus}</b>
          </div>
        </div>

        <button onClick={loadKey} style={{ height: 38 }}>
          Reload key
        </button>
      </div>

      <hr style={{ margin: "16px 0" }} />

      <div>
        <div>
          <b>Peer (IP:PORT)</b>
        </div>
        <input
          value={peer}
          onChange={(e) => setPeer(e.target.value)}
          style={{ width: "100%" }}
        />
      </div>

      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <input
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          placeholder="Message..."
          style={{ flex: 1 }}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button onClick={send}>Send (AES-GCM)</button>
      </div>

      <hr style={{ margin: "16px 0" }} />

      <h3>Inbox (live)</h3>
      <div
        style={{
          border: "1px solid #ddd",
          padding: 12,
          borderRadius: 8,
          minHeight: 160,
        }}
      >
        {messages.length === 0 ? (
          <div style={{ opacity: 0.7 }}>No messages yet</div>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              style={{ padding: "6px 0", borderBottom: "1px solid #eee" }}
            >
              {m}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
