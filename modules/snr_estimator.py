# modules/snr_estimator.py
import numpy as np
from scipy import signal
from rtma.messages import FilteredAccelMsg, SNRMsg


class SNREstimator:
    """
    Estimates SNR as the ratio of in-band (5–15 Hz) PSD power to
    out-of-band power — matching the LivePlot_V9 reference exactly.

    SNR (dB) = 10 * log10( P_signal / P_noise )
    where P_signal = sum(Pxx) in [5, 15] Hz
          P_noise  = sum(Pxx) outside that band
    Result is clipped to [−30, 40] dB.
    """

    FREQ_LOW  = 5.0
    FREQ_HIGH = 15.0
    SNR_MIN   = -30.0
    SNR_MAX   =  40.0

    def __init__(self, bus, fs=100):
        self.fs = fs
        self.bus = bus
        bus.subscribe(FilteredAccelMsg, self.on_filtered)

    # ------------------------------------------------------------------
    def on_filtered(self, msg: FilteredAccelMsg):
        mag_filt = np.asarray(msg.value, dtype=float)

        if len(mag_filt) < 64:
            return

        nperseg = min(128, len(mag_filt))
        try:
            f, Pxx = signal.welch(mag_filt, fs=self.fs, nperseg=nperseg)
        except Exception:
            return

        mask_signal = (f >= self.FREQ_LOW) & (f <= self.FREQ_HIGH)

        P_signal = float(np.sum(Pxx[mask_signal]))
        P_total  = float(np.sum(Pxx))
        P_noise  = P_total - P_signal

        if P_noise <= 0:
            P_noise = 1e-12

        snr_db = 10.0 * np.log10(P_signal / P_noise)
        snr_db = float(np.clip(snr_db, self.SNR_MIN, self.SNR_MAX))

        self.bus.publish(SNRMsg(t=msg.t, snr_db=snr_db))
        