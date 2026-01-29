# rtma/messages/base_msg.py
import time

class BaseMsg:
    def __init__(self, t=None):
        self.t = t if t is not None else time.time()
