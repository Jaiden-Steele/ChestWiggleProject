// dashboard/server.js

const express        = require("express");
const WebSocket      = require("ws");
const RTMASubscriber = require("./rtma_subscriber");
const zmq            = require("zeromq");

const ZMQ_SUB_ADDR  = "tcp://localhost:5555";  // Python PUB  → Node SUB
const ZMQ_PUSH_ADDR = "tcp://localhost:5556";  // Node PUSH   → Python PULL
const HTTP_PORT     = 3000;
const PING_MS       = 20_000;

const app = express();
app.use(express.static("public"));

const server = app.listen(HTTP_PORT, () => {
  console.log(`[Server] Dashboard at http://localhost:${HTTP_PORT}`);
});

const wss = new WebSocket.Server({ server });

// ── ZMQ PUSH socket (browser → Python) ──────────────────────────────────────
const pushSock = new zmq.Push();
pushSock.connect(ZMQ_PUSH_ADDR);
console.log(`[Server] ZMQ PUSH connected to ${ZMQ_PUSH_ADDR}`);

// ── Heartbeat ────────────────────────────────────────────────────────────────
function heartbeat() { this.isAlive = true; }

setInterval(() => {
  wss.clients.forEach((ws) => {
    if (!ws.isAlive) { ws.terminate(); return; }
    ws.isAlive = false;
    ws.ping();
  });
}, PING_MS);

// ── WebSocket connections ─────────────────────────────────────────────────────
wss.on("connection", (ws) => {
  console.log("[Server] Browser client connected");
  ws.isAlive = true;
  ws.on("pong",  heartbeat);
  ws.on("error", (err) => console.error("[WS] Client error:", err.message));
  ws.on("close", ()    => console.log("[Server] Browser client disconnected"));

  // Messages FROM the browser (e.g. reference frequency updates)
  ws.on("message", async (data) => {
    try {
      const packet = JSON.parse(data.toString());
      if (packet.topic === "SetReferenceFreq" && typeof packet.f_ref === "number") {
        console.log(`[Server] SetReferenceFreq → ${packet.f_ref} Hz`);
        await pushSock.send(JSON.stringify(packet));
      }
    } catch (err) {
      console.error("[WS] Message parse error:", err.message);
    }
  });
});

// ── ZMQ SUB → WebSocket forwarding ───────────────────────────────────────────
const rtma = new RTMASubscriber(ZMQ_SUB_ADDR);

rtma.listen((topic, msg) => {
  const packet = JSON.stringify({ topic, msg });
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(packet, (err) => {
        if (err) console.error("[WS] Send error:", err.message);
      });
    }
  });
});