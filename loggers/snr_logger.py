# loggers/snr_logger.py
import csv
from rtma.messages.snr_msg import SNRMsg

class SNRLogger:
    def __init__(self, bus, filename):
        self.f = open(filename, "w", newline="")
        self.writer = csv.writer(self.f)
        self.writer.writerow(["time_s", "snr_db"])
        bus.subscribe(SNRMsg, self.on_msg)

    def on_msg(self, msg):
        self.writer.writerow([msg.t, msg.snr_db])
        self.f.flush()
