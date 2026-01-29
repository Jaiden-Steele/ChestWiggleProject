# modules/frequency_error.py

# modules/frequency_error.py
from rtma.messages import FrequencyErrorMsg
from rtma.messages.reference_freq_msg import ReferenceFreqMsg
from rtma.messages.frequency_msg import FrequencyMsg

class FrequencyErrorCalculator:
    def __init__(self, bus):
        self.bus = bus
        self.ref = None
        bus.subscribe(ReferenceFreqMsg, self.on_ref)
        bus.subscribe(FrequencyMsg, self.on_freq)

    def on_ref(self, msg):
        self.ref = msg

    def on_freq(self, msg):
        if self.ref:
            err = abs(msg.f_hz - self.ref.f_ref)
            self.bus.publish(
                FrequencyErrorMsg(msg.t, err)
            )
