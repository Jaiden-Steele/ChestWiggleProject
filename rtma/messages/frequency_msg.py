# rtma/messages/frequency_msg.py

class FrequencyMsg:
    def __init__(self, t, f_hz):
        self.t = t
        self.f_hz = f_hz

    def to_dict(self):
        return {
            "t": self.t,
            "f_hz": self.f_hz
        }
