# modules/frequency_estimator.py
import numpy as np
from collections import deque
from scipy import signal
from scipy.signal import find_peaks
from rtma.messages import FilteredAccelMsg, FrequencyMsg


class FrequencyEstimator:
    """
    Estimates oscillation frequency from filtered acceleration windows.

    Matches the LivePlot_V9 reference approach:
      - Welch PSD on the filtered projection
      - Find most prominent peak in 5–15 Hz band
      - Fall back to centre-of-mass if no prominent peak found
      - 5-sample median smoother for temporal stability
      - Zero-crossing fallback if PSD returns 0 Hz
    """

    FREQ_LOW  = 5.0    # Hz  — HFOV physiological band (matches reference)
    FREQ_HIGH = 15.0   # Hz
    PROMINENCE_RATIO = 0.25   # peak must be ≥ 25 % of band-max power

    def __init__(self, fs, bus):
        self.fs = fs
        self.bus = bus
        self._freq_history = deque(maxlen=5)   # median smoother window
        bus.subscribe(FilteredAccelMsg, self.on_filtered)

    def on_filtered(self, msg: FilteredAccelMsg):
        mag_filt = np.asarray(msg.value, dtype=float)

        if len(mag_filt) < 64:
            return

        # --- Welch PSD ---
        nperseg = min(128, len(mag_filt))
        try:
            f, Pxx = signal.welch(mag_filt, fs=self.fs, nperseg=nperseg)
        except Exception:
            return

        # --- Restrict to HFOV band ---
        mask = (f >= self.FREQ_LOW) & (f <= self.FREQ_HIGH)
        f_band  = f[mask]
        Pxx_band = Pxx[mask]

        if len(Pxx_band) == 0 or np.max(Pxx_band) < 1e-6:
            return

        # --- Peak detection with prominence threshold ---
        peaks, props = find_peaks(
            Pxx_band,
            prominence=np.max(Pxx_band) * self.PROMINENCE_RATIO
        )

        if len(peaks) > 0:
            # Most prominent peak
            best = peaks[np.argmax(props['prominences'])]
            freq_raw = float(f_band[best])
        else:
            # Fall back: spectral centre-of-mass
            freq_raw = float(np.sum(f_band * Pxx_band) / np.sum(Pxx_band))

        # --- Temporal median smoothing ---
        self._freq_history.append(freq_raw)
        freq = float(np.median(self._freq_history))

        # --- Zero-crossing fallback ---
        if freq == 0.0:
            crossings = np.sum(
                (mag_filt[:-1] >= 0) & (mag_filt[1:] < 0) |
                (mag_filt[:-1] <  0) & (mag_filt[1:] >= 0)
            )
            freq = (crossings / 2.0) * self.fs / len(mag_filt)

        self.bus.publish(FrequencyMsg(t=msg.t, f_hz=freq))