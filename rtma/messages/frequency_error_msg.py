# rtma/messages/frequency_error_msg.py
from rtma.messages.base_msg import BaseMsg


class FrequencyErrorMsg(BaseMsg):
    def __init__(self, t, error_hz):
        super().__init__(t)
        self.error_hz = float(error_hz)

    def to_dict(self):
        return {"t": self.t, "error_hz": self.error_hz}