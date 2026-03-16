# modules/snr_estimator.py
import numpy as np
from scipy import signal
from rtma.messages import FilteredAccelMsg, ReferenceFreqMsg, SNRMsg


class SNREstimator:
    """
    Peak SNR estimator — compares the PSD peak power to the local noise
    floor around it, rather than signal-band vs everything-else.

    Method (matches how spectrum analysers measure SNR):
      1. Compute Welch PSD on the filtered window.
      2. Find the dominant peak in the 5-15 Hz band.
      3. Signal power  = mean Pxx in a narrow ±PEAK_BW window around peak.
      4. Noise floor   = median Pxx in the 5-15 Hz band EXCLUDING the
                         ±EXCLUDE_BW window around the peak.
                         Median is used (not mean) so harmonics don't
                         inflate the noise estimate.
      5. SNR (dB) = 10 * log10( P_signal / P_noise )

    Why this is better than band-ratio SNR:
      - Works regardless of where in 5-15 Hz the signal sits.
      - Noise floor is measured locally, so broadband noise outside the
        HFOV band doesn't affect the reading at all.
      - Gives a meaningful dB value: 0 dB = peak is at noise floor,
        10 dB = peak is 10x above noise floor.

    Amplitude gate: if RMS < MIN_AMP_MG the sensor is still — no publish.
    Result clipped to [-10, 40] dB.
    """

    FREQ_LOW   = 5.0    # Hz — HFOV band
    FREQ_HIGH  = 15.0   # Hz
    PEAK_BW    = 1.0    # Hz either side of peak = signal window
    EXCLUDE_BW = 2.0    # Hz either side of peak excluded from noise estimate
    MIN_AMP_MG = 10.0   # mg RMS — below this we are still
    SNR_MIN    = -10.0
    SNR_MAX    =  40.0

    def __init__(self, bus, fs=100):
        self.fs  = fs
        self.bus = bus
        bus.subscribe(FilteredAccelMsg, self.on_filtered)

    def on_filtered(self, msg: FilteredAccelMsg):
        mag_filt = np.asarray(msg.value, dtype=float)
        if len(mag_filt) < 64:
            return

        # Amplitude gate
        rms_mg = float(np.sqrt(np.mean(mag_filt ** 2))) * 1000.0
        if rms_mg < self.MIN_AMP_MG:
            return

        # Welch PSD
        nperseg = min(128, len(mag_filt))
        try:
            f, Pxx = signal.welch(mag_filt, fs=self.fs, nperseg=nperseg)
        except Exception:
            return

        # Restrict to HFOV band
        band_mask = (f >= self.FREQ_LOW) & (f <= self.FREQ_HIGH)
        f_band    = f[band_mask]
        Pxx_band  = Pxx[band_mask]

        if len(Pxx_band) < 4:
            return

        # Find dominant peak in band
        peak_idx = int(np.argmax(Pxx_band))
        f_peak   = float(f_band[peak_idx])

        # Signal window: ±PEAK_BW around peak
        sig_mask  = (f_band >= f_peak - self.PEAK_BW) & \
                    (f_band <= f_peak + self.PEAK_BW)
        P_signal  = float(np.mean(Pxx_band[sig_mask])) if np.any(sig_mask) else 0.0

        # Noise window: rest of band excluding ±EXCLUDE_BW around peak
        noise_mask = band_mask & \
                     ~((f >= f_peak - self.EXCLUDE_BW) &
                       (f <= f_peak + self.EXCLUDE_BW))
        Pxx_noise  = Pxx[noise_mask]

        if len(Pxx_noise) < 2:
            # Not enough noise samples — fall back to band edges only
            edge_mask  = band_mask & \
                         ~((f >= f_peak - self.EXCLUDE_BW) &
                           (f <= f_peak + self.EXCLUDE_BW))
            Pxx_noise  = Pxx[edge_mask] if np.any(edge_mask) else np.array([1e-12])

        # Median noise floor (robust to harmonics)
        P_noise = float(np.median(Pxx_noise)) if len(Pxx_noise) > 0 else 1e-12
        if P_noise <= 0:
            P_noise = 1e-12
        if P_signal <= 0:
            return

        snr_db = 10.0 * np.log10(P_signal / P_noise)
        snr_db = float(np.clip(snr_db, self.SNR_MIN, self.SNR_MAX))

        self.bus.publish(SNRMsg(t=msg.t, snr_db=snr_db))