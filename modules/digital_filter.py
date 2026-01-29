# modules/digital_filter.py
from rtma.messages import FilteredAccelMsg
from rtma.messages import AccelMsg

class DigitalFilter:
    def __init__(self, fs, bus):
        self.bus = bus
        bus.subscribe(AccelMsg, self.on_accel)

    def on_accel(self, accel_msg):
        y = accel_msg.az  # replace with real filter
        self.bus.publish(
            FilteredAccelMsg(accel_msg.t, y)
        )
