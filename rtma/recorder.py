# rtma/recorder.py
import csv

class RTMARecorder:
    def __init__(self, bus, filename="rtma_recording.csv"):
        self.f = open(filename, "w", newline="")
        self.writer = csv.writer(self.f)

        self.writer.writerow([
            "t",
            "msg_type",
            "payload"
        ])

        bus.subscribe_all(self.on_msg)

    def on_msg(self, msg):
        self.writer.writerow([
            msg.t,
            type(msg).__name__,
            msg.__dict__
        ])
        self.f.flush()

    def close(self):
        self.f.close()
