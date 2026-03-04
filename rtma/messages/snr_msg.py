# rtma/messages/snr_msg.py
from rtma.messages.base_msg import BaseMsg


class SNRMsg(BaseMsg):
    def __init__(self, t, snr_db):
        super().__init__(t)
        self.snr_db = float(snr_db)

    def to_dict(self):
        return {"t": self.t, "snr_db": self.snr_db}