const express = require("express");
const WebSocket = require("ws");
const RTMASubscriber = require("./rtma_subscriber");

const app = express();
app.use(express.static("public"));

const server = app.listen(3000, () => {
  console.log("Dashboard running at http://localhost:3000");
});

const wss = new WebSocket.Server({ server });

const rtma = new RTMASubscriber();

wss.on("connection", (ws) => {
  console.log("Dashboard client connected");
});

rtma.listen((topic, msg) => {
  const packet = JSON.stringify({
    topic,
    msg
  });

  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(packet);
    }
  });
});
