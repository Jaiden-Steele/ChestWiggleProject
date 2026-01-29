# modules/snr_estimator.py

import numpy as np
from collections import deque
from rtma.messages.filtered_accel_msg import FilteredAccelMsg
from rtma.messages.snr_msg import SNRMsg

class SNREstimator:
    def __init__(self, bus, fs=100):
        self.bus = bus
        self.fs = fs

        self.buffer = deque(maxlen=256)

        bus.subscribe(FilteredAccelMsg, self.on_filtered)

    def on_filtered(self, msg: FilteredAccelMsg):
        self.buffer.append(msg.value)  

        if len(self.buffer) < 128:
            return

        x = np.array(self.buffer)

        signal_power = np.mean(x**2)
        noise_power = np.var(x - np.mean(x))

        if noise_power <= 0:
            snr_db = -30.0
        else:
            snr_db = 10 * np.log10(signal_power / noise_power)

        self.bus.publish(
            SNRMsg(
                t=msg.t,
                snr_db=float(snr_db)
            )
        )
