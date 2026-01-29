const zmq = require("zeromq");
const msgpack = require("msgpack-lite");

class RTMASubscriber {
  constructor(address = "tcp://localhost:5555") {
    this.sock = new zmq.Subscriber();
    this.sock.connect(address);
    this.sock.subscribe(); // all topics
  }

  async listen(callback) {
    for await (const [topic, payload] of this.sock) {
      const msg = msgpack.decode(payload);
      callback(topic.toString(), msg);
    }
  }
}

module.exports = RTMASubscriber;
