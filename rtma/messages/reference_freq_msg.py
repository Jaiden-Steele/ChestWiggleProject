# rtma/messages/reference_freq_msg.py

class ReferenceFreqMsg:
    def __init__(self, t, f_ref):
        self.t = t
        self.f_ref = f_ref

    def to_dict(self):
        return {
            "t": self.t,
            "f_ref": self.f_ref
        }
