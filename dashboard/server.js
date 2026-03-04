// dashboard/server.js
// Express + WebSocket bridge between ZMQ (Python) and browser clients.
//
// Long-run fixes vs original:
//   - All per-message console.log removed (was logging 100+ times/sec).
//   - WebSocket ping/pong heartbeat: stale browser tabs are detected and
//     terminated so the client list never fills with dead sockets.
//   - ws.on("error") handler prevents uncaught exceptions crashing Node.
//   - RTMASubscriber receives the address argument correctly.

const express   = require("express");
const WebSocket = require("ws");
const RTMASubscriber = require("./rtma_subscriber");

const ZMQ_ADDR   = "tcp://localhost:5555";
const HTTP_PORT  = 3000;
const PING_MS    = 20_000;   // send a WS ping every 20 s

const app = express();
app.use(express.static("public"));

const server = app.listen(HTTP_PORT, () => {
  console.log(`[Server] Dashboard at http://localhost:${HTTP_PORT}`);
});

const wss = new WebSocket.Server({ server });

// ---------------------------------------------------------------------------
// Heartbeat — terminate zombie connections that won't affect experiment data
// ---------------------------------------------------------------------------
function heartbeat() { this.isAlive = true; }

setInterval(() => {
  wss.clients.forEach((ws) => {
    if (!ws.isAlive) {
      ws.terminate();
      return;
    }
    ws.isAlive = false;
    ws.ping();
  });
}, PING_MS);

wss.on("connection", (ws) => {
  console.log("[Server] Browser client connected");
  ws.isAlive = true;
  ws.on("pong",  heartbeat);
  ws.on("error", (err) => console.error("[WS] Client error:", err.message));
  ws.on("close", ()    => console.log("[Server] Browser client disconnected"));
});

// ---------------------------------------------------------------------------
// ZMQ → WebSocket forwarding
// ---------------------------------------------------------------------------
const rtma = new RTMASubscriber(ZMQ_ADDR);

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