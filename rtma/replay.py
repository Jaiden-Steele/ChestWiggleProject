# rtma/replay.py
import csv
import time

class RTMAReplay:
    def __init__(self, bus, filename):
        self.bus = bus
        self.filename = filename

    def run(self):
        with open(self.filename, newline="") as f:
            reader = csv.DictReader(f)
            start = None

            for row in reader:
                if start is None:
                    start = float(row["time_s"])

                dt = float(row["time_s"]) - start
                time.sleep(dt)

                # reconstruct message here
                # bus.publish(msg)
