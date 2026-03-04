# modules/digital_filter.py
import numpy as np
from scipy import signal
from collections import deque
from rtma.messages import AccelMsg, FilteredAccelMsg


class DigitalFilter:
    """
    Buffers raw AccelMsg samples, applies DC removal, PCA projection onto
    the dominant vibration axis, and a 4th-order Butterworth bandpass
    (3–20 Hz) matching the LivePlot_V9 reference.

    Publishes a FilteredAccelMsg once per STRIDE new samples (default 20,
    i.e. 5 Hz at fs=100) rather than on every single sample.  This keeps
    the downstream Welch PSD running at a sensible rate without wasting
    CPU reprocessing an almost-identical 200-sample window 100 times/sec.

    Long-run robustness:
      - All numpy ops wrapped in try/except; malformed windows are silently
        dropped rather than crashing the module.
      - Buffer is a fixed-size deque so memory never grows.
    """

    MIN_RAW_AMP_MG = 3.0   # below this the signal is just sensor noise

    def __init__(self, fs, bus, window=200, stride=20):
        self.fs     = fs
        self.bus    = bus
        self.window = window
        self.stride = stride
        self._since_last = 0   # samples accumulated since last publish

        # Fixed-size ring buffers — never leak memory
        self._ax = deque(maxlen=window)
        self._ay = deque(maxlen=window)
        self._az = deque(maxlen=window)
        self._ts = deque(maxlen=window)

        # 4th-order Butterworth bandpass 3–20 Hz (matches reference)
        self._sos = signal.butter(4, [3, 20], btype="band", fs=fs, output="sos")

        bus.subscribe(AccelMsg, self.on_accel)

    # ------------------------------------------------------------------
    def on_accel(self, msg: AccelMsg):
        self._ts.append(msg.t)
        self._ax.append(msg.ax)
        self._ay.append(msg.ay)
        self._az.append(msg.az)
        self._since_last += 1

        # Wait until the buffer is full AND a full stride has arrived
        if len(self._ax) < self.window or self._since_last < self.stride:
            return

        self._since_last = 0
        self._process()

    # ------------------------------------------------------------------
    def _process(self):
        try:
            ax = np.array(self._ax, dtype=float)
            ay = np.array(self._ay, dtype=float)
            az = np.array(self._az, dtype=float)

            # Guard: reject windows containing NaN
            if np.any(np.isnan(ax)) or np.any(np.isnan(ay)) or np.any(np.isnan(az)):
                return

            # Clip sensor spikes (±4 g)
            ax = np.clip(ax, -4, 4)
            ay = np.clip(ay, -4, 4)
            az = np.clip(az, -4, 4)

            # Remove DC / gravity offset per axis
            ax_ac = ax - np.mean(ax)
            ay_ac = ay - np.mean(ay)
            az_ac = az - np.mean(az)

            # PCA: project onto dominant vibration direction
            try:
                X   = np.stack([ax_ac, ay_ac, az_ac], axis=1)  # (N, 3)
                cov = np.cov(X, rowvar=False)
                eigvals, eigvecs = np.linalg.eigh(cov)
                u   = eigvecs[:, np.argmax(eigvals)]
                mag_proj = X @ u                                 # (N,)
            except Exception:
                mag_proj = np.sqrt(ax_ac**2 + ay_ac**2 + az_ac**2)

            # Reject weak signals before filtering
            if np.std(mag_proj) * 1000.0 < self.MIN_RAW_AMP_MG:
                return

            # Bandpass filter
            mag_filt = signal.sosfiltfilt(self._sos, mag_proj)

            # Publish the full filtered window; downstream uses it for PSD.
            self.bus.publish(
                FilteredAccelMsg(t=self._ts[-1], value=mag_filt)
            )

        except Exception:
            # Never let a processing error silently kill the module
            pass