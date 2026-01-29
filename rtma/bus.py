class RTMABus:
    def __init__(self):
        self.subscribers = {}
        self.global_subscribers = []   # <-- NEW

    def subscribe(self, msg_type, callback):
        self.subscribers.setdefault(msg_type, []).append(callback)

    def subscribe_all(self, callback):
        """Subscribe to all messages (used by recorders, debuggers)."""
        self.global_subscribers.append(callback)

    def publish(self, msg):
        # Message-type-specific subscribers
        for cb in self.subscribers.get(type(msg), []):
            cb(msg)

        # Global subscribers (recorders, monitors)
        for cb in self.global_subscribers:
            cb(msg)
