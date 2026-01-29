# loggers/frequency_error_logger.py
import csv
from rtma.messages.frequency_error_msg import FrequencyErrorMsg

class FrequencyErrorLogger:
    def __init__(self, bus, filename="frequency_error.csv"):
        self.f = open(filename, "w", newline="")
        self.writer = csv.writer(self.f)
        self.writer.writerow(["time_s", "error_hz"])

        bus.subscribe(FrequencyErrorMsg, self.on_msg)

    def on_msg(self, msg):
        self.writer.writerow([msg.t, msg.error_hz])
        self.f.flush()

