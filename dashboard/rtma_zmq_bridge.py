# dashboard/rtma_zmq_bridge.py
"""
ZMQ bridge: forwards RTMA bus messages to a ZMQ PUB socket so the
Node.js dashboard can subscribe.

Long-run robustness fixes:
  - JSON serialisation is numpy-safe (converts ndarray → list).
  - FilteredAccelMsg (200-sample array at 5 Hz) is NOT forwarded — it
    would push ~40 KB/s of JSON to the browser for no benefit, since
    the dashboard only needs the scalar amplitude for display.
    The bridge sends a lightweight AmplitudeMsg-style packet instead.
  - Debug print removed; only errors are logged.
  - ZMQ SNDHWM set so a slow subscriber can't exhaust Python memory.
"""

import socket as _socket
import numpy as np
import zmq


class RTMAZMQBridge:

    # Topics whose payload is a large array — send a slimmed-down version
    _ARRAY_TOPICS = {"FilteredAccelMsg"}

    def __init__(self, bus, addr=None):
        self.bus     = bus
        self.context = zmq.Context()
        self.sock    = self.context.socket(zmq.PUB)
        self.sock.setsockopt(zmq.LINGER,  0)
        self.sock.setsockopt(zmq.SNDHWM, 100)   # drop old frames if subscriber slow

        if addr is None:
            port = self._find_free_port(5555)
            addr = f"tcp://*:{port}"
            print(f"[RTMAZMQBridge] Binding on port {port}")

        self.sock.bind(addr)
        bus.subscribe_all(self._forward_message)
        print(f"[RTMAZMQBridge] Ready on {addr}")

    # ------------------------------------------------------------------
    def _find_free_port(self, start=5555, max_tries=100):
        for port in range(start, start + max_tries):
            with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No free port found in range.")

    # ------------------------------------------------------------------
    def _to_serialisable(self, obj):
        """Recursively convert numpy types to plain Python."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, dict):
            return {k: self._to_serialisable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._to_serialisable(v) for v in obj]
        return obj

    # ------------------------------------------------------------------
    def _forward_message(self, msg):
        try:
            topic = type(msg).__name__

            # For FilteredAccelMsg send only the scalar amplitude (std of
            # the filtered window in mg) — not the full 200-sample array.
            if topic in self._ARRAY_TOPICS:
                arr = np.asarray(msg.value, dtype=float)
                amp = float(np.std(arr) * 1000.0)
                packet = {"topic": topic, "msg": {"t": float(msg.t), "value": amp}}
            else:
                if hasattr(msg, "to_dict"):
                    raw = msg.to_dict()
                elif hasattr(msg, "__dict__"):
                    raw = {k: v for k, v in msg.__dict__.items()
                           if not k.startswith("_")}
                else:
                    raw = {}
                packet = {"topic": topic, "msg": self._to_serialisable(raw)}

            self.sock.send_json(packet, flags=zmq.NOBLOCK)

        except zmq.Again:
            pass   # subscriber too slow — frame dropped, experiment continues
        except Exception as e:
            print(f"[RTMAZMQBridge] Error forwarding {type(msg).__name__}: {e}")