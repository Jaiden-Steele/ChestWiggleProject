const zmq = require("zeromq");

class RTMASubscriber {
  constructor() {
    this.sock = new zmq.Subscriber();
    this.sock.connect("tcp://127.0.0.1:5555");  // MUST match RTMA bus
    this.sock.subscribe("");
    console.log("📡 RTMA subscriber connected");
  }

  async listen(callback) {
    for await (const [msg] of this.sock) {
      const text = msg.toString();
      console.log("📥 RAW RTMA:", text);

      const parsed = JSON.parse(text);
      callback(parsed.topic, parsed.msg);
    }
  }
}

module.exports = RTMASubscriber;
