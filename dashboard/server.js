const express = require("express");
const WebSocket = require("ws");
const RTMASubscriber = require("./rtma_subscriber");

const app = express();
app.use(express.static("public"));

const server = app.listen(3000, () => {
  console.log("Dashboard running at http://localhost:3000");
});

const wss = new WebSocket.Server({ server });

// Connect to ZMQ (make sure port matches your Python RTMAZMQBridge)
const rtma = new RTMASubscriber("tcp://localhost:5555");

wss.on("connection", (ws) => {
  console.log("Dashboard client connected");
  
  // Send a test message to the newly connected client
  ws.send(JSON.stringify({ 
    topic: "ServerTest", 
    msg: { message: "Hello from server!" } 
  }));

  ws.on("close", () => {
    console.log("Dashboard client disconnected");
  });
});

// Forward every RTMA message to all connected WebSocket clients
rtma.listen((topic, msg) => {
  console.log("➡ RTMA EVENT RECEIVED IN NODE:", topic, msg);

  const packet = JSON.stringify({ topic, msg });
  
  console.log(`[WS] Broadcasting to ${wss.clients.size} clients`);
  
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      console.log("[WS] Sending packet to client");
      client.send(packet);
    } else {
      console.log("[WS] Client not ready, state:", client.readyState);
    }
  });
});