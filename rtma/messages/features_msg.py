"""
Module: rtma.messages.features_msg
Defines the FeaturesMsg class for RTMA messaging.
"""

class FeaturesMsg:
    def __init__(self, freq, amp):
        self.freq = freq
        self.amp = amp

    def to_dict(self):
        return self.__dict__