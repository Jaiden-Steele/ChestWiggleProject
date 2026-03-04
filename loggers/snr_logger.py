# loggers/snr_logger.py
"""
Buffered SNR logger.  Flushes every FLUSH_INTERVAL seconds instead of
after every row, preventing excessive fsync overhead during long experiments.
"""
import csv
import time
from rtma.messages.snr_msg import SNRMsg


class SNRLogger:
    FLUSH_INTERVAL = 5.0

    def __init__(self, bus, filename="snr_log.csv"):
        self.f      = open(filename, "w", newline="")
        self.writer = csv.writer(self.f)
        self.writer.writerow(["time_s", "snr_db"])
        self._last_flush = time.monotonic()
        bus.subscribe(SNRMsg, self.on_msg)

    def on_msg(self, msg):
        self.writer.writerow([msg.t, msg.snr_db])
        now = time.monotonic()
        if now - self._last_flush >= self.FLUSH_INTERVAL:
            self.f.flush()
            self._last_flush = now

    def close(self):
        self.f.flush()
        self.f.close()