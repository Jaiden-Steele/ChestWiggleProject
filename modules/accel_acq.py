"""Module: accel_acq
Role: Acquires accelerometer data from serial port.

Long-run robustness fixes vs original:
  - poll() drains ALL available bytes each tick (not just one sample).
  - Automatic serial reconnect on IOError so a cable wobble doesn't kill
    a 2-hour experiment.
  - Decode errors are swallowed per-line so a corrupt byte never crashes.
  - Prints are rate-limited so the terminal doesn't flood at 100 Hz.
"""

import time
import serial
import serial.tools.list_ports
from rtma.messages import AccelMsg


class AccelAcq:
    RECONNECT_DELAY   = 2.0   # seconds to wait before retrying after disconnect
    MAX_LINES_PER_TICK = 50   # safety cap: don't spin forever if buffer is huge

    def __init__(self, bus, fs=100):
        self.bus  = bus
        self.fs   = fs
        self.n    = 0
        self._baudrate = 115200
        self._port     = None        # discovered on first connect
        self.ser       = self._connect()
        self._last_warn = 0.0        # rate-limit error prints

    # ------------------------------------------------------------------
    def _connect(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            raise RuntimeError("No serial devices found. Is the accelerometer plugged in?")

        self._port = ports[0].device
        ser = serial.Serial(self._port, self._baudrate, timeout=0.01)
        time.sleep(2)
        ser.flushInput()
        print(f"[AccelAcq] Connected to {self._port}")
        return ser

    def _reconnect(self):
        """Called after a serial error.  Keeps trying until port comes back."""
        now = time.monotonic()
        if now - self._last_warn > 5.0:
            print(f"[AccelAcq] Serial lost — attempting reconnect on {self._port} …")
            self._last_warn = now
        try:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
            time.sleep(self.RECONNECT_DELAY)
            self.ser = self._connect()
            print("[AccelAcq] Reconnected successfully.")
        except Exception as e:
            self.ser = None
            print(f"[AccelAcq] Reconnect failed: {e}")

    # ------------------------------------------------------------------
    def poll(self):
        """Drain all available serial data and publish an AccelMsg for each
        valid CSV triple.  Returns the number of samples published."""
        if not self.ser or not self.ser.is_open:
            self._reconnect()
            return 0

        published = 0
        try:
            for _ in range(self.MAX_LINES_PER_TICK):
                if not self.ser.in_waiting:
                    break

                raw = self.ser.readline()
                line = raw.decode("utf-8", errors="replace").strip()

                if not line or line.startswith("#"):
                    continue

                parts = line.split(",")
                if len(parts) != 3:
                    continue

                try:
                    ax, ay, az = float(parts[0]), float(parts[1]), float(parts[2])
                except ValueError:
                    continue

                msg = AccelMsg(time.monotonic(), ax, ay, az)
                self.bus.publish(msg)
                self.n += 1
                published += 1

        except (serial.SerialException, OSError):
            self._reconnect()

        return published