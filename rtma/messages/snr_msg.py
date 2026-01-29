# rtma/messages/snr_msg.py
from rtma.messages.base_msg import BaseMsg

class SNRMsg(BaseMsg):
    def __init__(self, t, snr_db):
        super().__init__(t)
        self.snr_db = snr_db
