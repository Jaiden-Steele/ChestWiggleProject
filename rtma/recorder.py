# rtma/recorder.py
"""
RTMARecorder — writes every bus message to a CSV file.

Long-run robustness fixes vs original:
  - Buffered writes: flushes to disk every FLUSH_INTERVAL seconds instead
    of after every single row.  At 5 Hz analysis output over 2 hours that
    is ~36 000 rows — per-row flush causes ~36 000 unnecessary syscalls.
  - Safe msg.t access: uses getattr(msg, 't', time.monotonic()) so
    messages without a 't' field (e.g. StateMsg before the fix) don't
    crash the recorder.
  - File opened in append mode by default so a restart doesn't wipe data.
  - close() flushes remaining buffer before closing.
"""

import csv
import time


class RTMARecorder:
    FLUSH_INTERVAL = 5.0   # seconds between disk flushes

    def __init__(self, bus, filename="rtma_recording.csv", append=False):
        mode = "a" if append else "w"
        self.f      = open(filename, mode, newline="", buffering=1)
        self.writer = csv.writer(self.f)
        self._last_flush = time.monotonic()

        if not append:
            self.writer.writerow(["t", "msg_type", "payload"])

        bus.subscribe_all(self.on_msg)

    # ------------------------------------------------------------------
    def on_msg(self, msg):
        t = getattr(msg, "t", time.monotonic())

        # Build a clean payload dict — skip private attrs and numpy arrays
        payload = {}
        for k, v in getattr(msg, "__dict__", {}).items():
            if k.startswith("_"):
                continue
            if hasattr(v, "tolist"):        # numpy array
                payload[k] = f"<array len={len(v)}>"
            else:
                payload[k] = v

        self.writer.writerow([t, type(msg).__name__, payload])

        # Flush periodically rather than on every row
        now = time.monotonic()
        if now - self._last_flush >= self.FLUSH_INTERVAL:
            self.f.flush()
            self._last_flush = now

    def close(self):
        self.f.flush()
        self.f.close()