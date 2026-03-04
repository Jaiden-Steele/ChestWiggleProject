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

    Publishes a FilteredAccelMsg containing the projected, filtered sample
    array each time the buffer is full (every `window` samples).
    """

    MIN_RAW_AMP_MG = 3.0   # below this the signal is just noise

    def __init__(self, fs, bus, window=200):
        self.fs = fs
        self.bus = bus
        self.window = window

        # Ring buffer – 200 samples = 2 s at 100 Hz (matches reference wave_size)
        self._ax = deque(maxlen=window)
        self._ay = deque(maxlen=window)
        self._az = deque(maxlen=window)
        self._ts = deque(maxlen=window)   # timestamps

        # 4th-order Butterworth bandpass 3–20 Hz (matches reference self.sos)
        self._sos = signal.butter(4, [3, 20], btype='band', fs=fs, output='sos')

        bus.subscribe(AccelMsg, self.on_accel)

    # ------------------------------------------------------------------
    def on_accel(self, msg: AccelMsg):
        # Accumulate samples
        self._ts.append(msg.t)
        self._ax.append(msg.ax)
        self._ay.append(msg.ay)
        self._az.append(msg.az)

        # Only process once the buffer is full
        if len(self._ax) < self.window:
            return

        ax = np.array(self._ax, dtype=float)
        ay = np.array(self._ay, dtype=float)
        az = np.array(self._az, dtype=float)

        # --- Guard: reject NaN samples ---
        if np.any(np.isnan(ax)) or np.any(np.isnan(ay)) or np.any(np.isnan(az)):
            return

        # --- Clip spikes (±4 g, same as reference) ---
        ax = np.clip(ax, -4, 4)
        ay = np.clip(ay, -4, 4)
        az = np.clip(az, -4, 4)

        # --- Remove DC (gravity) from each axis ---
        ax_ac = ax - np.mean(ax)
        ay_ac = ay - np.mean(ay)
        az_ac = az - np.mean(az)

        # --- PCA: project onto dominant vibration direction ---
        try:
            X = np.stack([ax_ac, ay_ac, az_ac], axis=1)   # (N, 3)
            cov = np.cov(X, rowvar=False)
            eigvals, eigvecs = np.linalg.eigh(cov)
            u = eigvecs[:, np.argmax(eigvals)]             # dominant axis
            mag_proj = X @ u                               # (N,)
        except Exception:
            mag_proj = np.sqrt(ax_ac**2 + ay_ac**2 + az_ac**2)

        # --- Reject weak signals before filtering ---
        raw_amp_mg = np.std(mag_proj) * 1000.0
        if raw_amp_mg < self.MIN_RAW_AMP_MG:
            return

        # --- Bandpass filter ---
        try:
            mag_filt = signal.sosfiltfilt(self._sos, mag_proj)
        except Exception:
            return

        # Publish the filtered projection array as a single message.
        # Downstream modules (FrequencyEstimator, SNREstimator) receive
        # the full window so they can run their own PSD analysis.
        self.bus.publish(
            FilteredAccelMsg(t=self._ts[-1], value=mag_filt)
        )