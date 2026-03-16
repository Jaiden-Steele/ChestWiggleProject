# dashboard/rtma_zmq_bridge.py
"""
ZMQ bridge: two sockets.
  - PUB on port 5555: forwards all RTMA bus messages to Node.js (unchanged).
  - PULL on port 5556: receives commands FROM Node.js (e.g. SetReferenceFreq)
    and dispatches them to the Python bus.

The PULL socket is polled non-blocking inside _forward_message so it never
blocks the Python main loop. Call poll_commands() from your main loop for
slightly lower latency, or rely on the automatic check inside _forward_message.
"""

import json
import socket as _socket
import threading
import numpy as np
import zmq

from rtma.messages import ReferenceFreqMsg


class RTMAZMQBridge:

    _ARRAY_TOPICS = {"FilteredAccelMsg"}

    def __init__(self, bus, pub_addr=None, pull_addr="tcp://*:5556"):
        self.bus     = bus
        self.context = zmq.Context()

        # ── PUB socket (Python → Node) ────────────────────────────────────
        self.pub = self.context.socket(zmq.PUB)
        self.pub.setsockopt(zmq.LINGER,  0)
        self.pub.setsockopt(zmq.SNDHWM, 100)

        if pub_addr is None:
            port    = self._find_free_port(5555)
            pub_addr = f"tcp://*:{port}"
            print(f"[RTMAZMQBridge] PUB binding on port {port}")

        self.pub.bind(pub_addr)

        # ── PULL socket (Node → Python) ───────────────────────────────────
        self.pull = self.context.socket(zmq.PULL)
        self.pull.setsockopt(zmq.LINGER, 0)
        self.pull.bind(pull_addr)
        print(f"[RTMAZMQBridge] PULL binding on {pull_addr}")

        # Background thread drains the PULL socket continuously
        self._stop  = False
        self._thread = threading.Thread(target=self._pull_loop, daemon=True)
        self._thread.start()

        bus.subscribe_all(self._forward_message)
        print(f"[RTMAZMQBridge] Ready — PUB on {pub_addr}, PULL on {pull_addr}")

    # ── PULL receiver loop (runs in background thread) ────────────────────
    def _pull_loop(self):
        while not self._stop:
            try:
                # Block with a short timeout so we can check _stop
                if self.pull.poll(timeout=200):
                    raw = self.pull.recv_string(flags=zmq.NOBLOCK)
                    self._handle_command(raw)
            except zmq.Again:
                pass
            except Exception as e:
                print(f"[RTMAZMQBridge] PULL error: {e}")

    def _handle_command(self, raw: str):
        try:
            packet = json.loads(raw)
            if packet.get("topic") == "SetReferenceFreq":
                f_ref = float(packet["f_ref"])
                print(f"[RTMAZMQBridge] Reference frequency updated → {f_ref} Hz")
                import time
                self.bus.publish(ReferenceFreqMsg(t=time.monotonic(), f_ref=f_ref))
        except Exception as e:
            print(f"[RTMAZMQBridge] Command parse error: {e}")

    # ── PUB forwarder ─────────────────────────────────────────────────────
    def _find_free_port(self, start=5555, max_tries=100):
        for port in range(start, start + max_tries):
            with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No free port found in range.")

    def _to_serialisable(self, obj):
        if isinstance(obj, np.ndarray):     return obj.tolist()
        if isinstance(obj, np.integer):     return int(obj)
        if isinstance(obj, np.floating):    return float(obj)
        if isinstance(obj, dict):           return {k: self._to_serialisable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):  return [self._to_serialisable(v) for v in obj]
        return obj

    def _forward_message(self, msg):
        if msg is None:
            return
        try:
            topic = type(msg).__name__

            if topic in self._ARRAY_TOPICS:
                arr = np.asarray(msg.value, dtype=float)
                amp = float(np.std(arr) * 1000.0)
                packet = {"topic": topic, "msg": {"t": float(msg.t), "value": amp}}
            else:
                raw = msg.to_dict() if hasattr(msg, "to_dict") else {
                    k: v for k, v in msg.__dict__.items() if not k.startswith("_")
                }
                packet = {"topic": topic, "msg": self._to_serialisable(raw)}

            self.pub.send_json(packet, flags=zmq.NOBLOCK)

        except zmq.Again:
            pass
        except Exception as e:
            print(f"[RTMAZMQBridge] Forward error for {type(msg).__name__}: {e}")

    def close(self):
        self._stop = True
        self._thread.join(timeout=1)
        self.pub.close()
        self.pull.close()
        self.context.term()