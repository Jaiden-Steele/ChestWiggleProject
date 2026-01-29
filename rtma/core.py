"""
module: core
role: Core RTMA functionality
"""

import zmq
import msgpack


class RTMA:
    def __init__(self, pub_addr="tcp://*:5555"):
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.PUB)
        self.sock.bind(pub_addr)

    def start(self):
        pass  # placeholder for symmetry with lab RTMA

    def publish(self, topic, msg):
        payload = msgpack.packb(msg.to_dict(), use_bin_type=True)
        self.sock.send_multipart([
            topic.encode("utf-8"),
            payload
        ])
