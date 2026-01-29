# modules/reference_freq.py
from rtma.messages import ReferenceFreqMsg

class ReferenceFrequency:
    def __init__(self, f_ref):
        self.f_ref = f_ref

    def update(self, t):
        return ReferenceFreqMsg(t, self.f_ref)
