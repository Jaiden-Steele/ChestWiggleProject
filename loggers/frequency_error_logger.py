# loggers/frequency_error_logger.py
"""
Buffered frequency-error logger.
"""
import csv
import time
from rtma.messages.frequency_error_msg import FrequencyErrorMsg


class FrequencyErrorLogger:
    FLUSH_INTERVAL = 5.0

    def __init__(self, bus, filename="frequency_error.csv"):
        self.f      = open(filename, "w", newline="")
        self.writer = csv.writer(self.f)
        self.writer.writerow(["time_s", "error_hz"])
        self._last_flush = time.monotonic()
        bus.subscribe(FrequencyErrorMsg, self.on_msg)

    def on_msg(self, msg):
        self.writer.writerow([msg.t, msg.error_hz])
        now = time.monotonic()
        if now - self._last_flush >= self.FLUSH_INTERVAL:
            self.f.flush()
            self._last_flush = now

    def close(self):
        self.f.flush()
        self.f.close()