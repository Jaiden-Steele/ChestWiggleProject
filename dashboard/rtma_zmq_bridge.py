import zmq
import socket

class RTMAZMQBridge:
    def __init__(self, bus, addr=None):
        self.bus = bus
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PUB)

        if addr is None:
            port = self._find_free_port(start=5555)
            addr = f"tcp://*:{port}"
            print(f"[RTMAZMQBridge] Using auto-selected port: {port}")

        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.bind(addr)
        
        # Use subscribe_all like the recorder does!
        bus.subscribe_all(self._forward_message)
        
        print(f"[RTMAZMQBridge] Subscribed to all messages on {addr}")

    def _find_free_port(self, start=5555, max_tries=100):
        for port in range(start, start + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No free ports found in the range")

    def _forward_message(self, msg):
        """Callback that forwards RTMA messages to ZMQ"""
        try:
            msg_type = type(msg).__name__
            
            # Extract message data
            if hasattr(msg, '__dict__'):
                msg_data = {k: v for k, v in msg.__dict__.items() if not k.startswith('_')}
            else:
                msg_data = {}
            
            packet = {
                "topic": msg_type,
                "msg": msg_data
            }
            
            self.sock.send_json(packet)
            print(f"[ZMQ] Forwarded {msg_type}")
            
        except Exception as e:
            print(f"[ZMQ ERROR] {e}")
            import traceback
            traceback.print_exc()