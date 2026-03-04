# rtma/messages/state_msg.py
import time


class StateMsg:
    """
    Carries the current system state integer.
      0 = NORMAL
      1 = LOW_SIGNAL
      2 = FAULT

    Adds a timestamp field so RTMARecorder (which calls msg.t on every
    message) doesn't raise AttributeError.
    """

    def __init__(self, state, t=None):
        self.state = int(state)
        self.t     = t if t is not None else time.monotonic()

    def to_dict(self):
        return {"t": self.t, "state": self.state}