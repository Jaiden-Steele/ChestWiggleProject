// dashboard/rtma_subscriber.js
// Connects to the Python ZMQ PUB socket and forwards parsed messages
// via a callback.
//
// Fixes vs original:
//   - Constructor accepts the address argument (was ignored before).
//   - Per-message console.log removed; errors only.

const zmq = require("zeromq");

class RTMASubscriber {
  constructor(addr = "tcp://127.0.0.1:5555") {
    this.sock = new zmq.Subscriber();
    this.sock.connect(addr);
    this.sock.subscribe("");   // subscribe to all topics
    console.log(`[RTMASubscriber] Connected to ${addr}`);
  }

  async listen(callback) {
    try {
      for await (const [frame] of this.sock) {
        try {
          const parsed = JSON.parse(frame.toString());
          callback(parsed.topic, parsed.msg);
        } catch (parseErr) {
          console.error("[RTMASubscriber] Parse error:", parseErr.message);
        }
      }
    } catch (err) {
      console.error("[RTMASubscriber] Socket error:", err.message);
    }
  }
}

module.exports = RTMASubscriber;