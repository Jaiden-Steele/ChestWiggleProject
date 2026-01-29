# modules/frequency_estimator.py
from rtma.messages import FilteredAccelMsg
from rtma.messages import FrequencyMsg

import numpy as np

class FrequencyEstimator:
    def __init__(self, fs, bus):
        self.bus = bus
        self.fs = fs
        self.buffer = []
        bus.subscribe(FilteredAccelMsg, self.on_filtered)

    def on_filtered(self, msg):
        self.buffer.append(msg.value)

        if len(self.buffer) < 256:
            return

        x = np.array(self.buffer)
        self.buffer.clear()

        fft = np.fft.rfft(x)
        freqs = np.fft.rfftfreq(len(x), d=1/self.fs)
        f_est = freqs[np.argmax(np.abs(fft))]

        self.bus.publish(FrequencyMsg(msg.t, float(f_est)))
