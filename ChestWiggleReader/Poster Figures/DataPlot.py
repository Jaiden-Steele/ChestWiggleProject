import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
import pandas as pd

# Load CSV (upload your file and put the name here)
df = pd.read_csv("recorded_data.csv")

ax = df["ax"].values
ay = df["ay"].values
az = df["az"].values

fs = 100
t = np.arange(len(ax)) / fs

# magnitude
mag = np.sqrt(ax**2 + ay**2 + az**2)

# remove DC
mag_dc = mag - np.mean(mag)

# bandpass filter
sos = signal.butter(4, [5, 15], btype="band", fs=fs, output="sos")
mag_filt = signal.sosfiltfilt(sos, mag_dc)

# spectrum
freqs, psd = signal.welch(mag_filt, fs)

# FIGURE 1: Raw vs filtered
plt.figure(figsize=(12,4))
plt.plot(t, mag_dc, alpha=0.5, label="Raw")
plt.plot(t, mag_filt, label="Filtered 5–15 Hz", linewidth=2)
plt.legend(); plt.grid(); plt.tight_layout()
plt.savefig("real_waveform.png", dpi=300)

# FIGURE 2: Spectrum
plt.figure(figsize=(10,4))
plt.plot(freqs, 10*np.log10(psd))
plt.title("Power Spectrum (Real Data)")
plt.xlabel("Hz"); plt.ylabel("Power (dB)")
plt.grid()
plt.tight_layout()
plt.savefig("real_spectrum.png", dpi=300)

print("Saved real_waveform.png and real_spectrum.png")
