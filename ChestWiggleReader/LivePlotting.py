import serial
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, filtfilt, lfilter

# --- Serial setup ---
ser = serial.Serial('COM3', 115200, timeout=1)  # change COM port if needed

# --- Plot setup ---
plt.style.use('ggplot')
fig, axs = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
window_size = 400  # number of samples shown in rolling window

# --- Buffers ---
time_vals, ax_vals, ay_vals, az_vals, mag_vals = [], [], [], [], []

# --- Band-pass filter (5–15 Hz) ---
def make_bandpass(lowcut=5, highcut=15, fs=100, order=4):
    nyquist = 0.5 * fs
    low, high = lowcut / nyquist, highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

b, a = make_bandpass()

def apply_bandpass_rolling(data):
    """Apply filter only if enough data points exist."""
    if len(data) < 25:
        return np.zeros_like(data)
    # use lfilter for rolling low-latency effect
    return lfilter(b, a, data)

# --- Initialize lines ---
lines = {}
lines['ax_raw'], = axs[0].plot([], [], label='Ax (raw)')
lines['ay_raw'], = axs[0].plot([], [], label='Ay (raw)')
lines['az_raw'], = axs[0].plot([], [], label='Az (raw)')
axs[0].set_ylabel('Raw Accel')
axs[0].legend(loc='upper right')

lines['ax_filt'], = axs[1].plot([], [], label='Ax (filt)')
lines['ay_filt'], = axs[1].plot([], [], label='Ay (filt)')
lines['az_filt'], = axs[1].plot([], [], label='Az (filt)')
axs[1].set_ylabel('Filtered')
axs[1].legend(loc='upper right')

lines['mag_raw'], = axs[2].plot([], [], 'k', label='Raw Mag')
lines['mag_filt'], = axs[2].plot([], [], 'b', label='Filtered Mag')
lines['threshold'], = axs[2].plot([], [], 'r--', label='Threshold')
axs[2].set_ylabel('Magnitude')
axs[2].legend(loc='upper right')

lines['crossings'], = axs[3].plot([], [], 'm', label='Crossings')
axs[3].set_ylabel('Events')
axs[3].set_xlabel('Time (ms)')
axs[3].legend(loc='upper right')

for ax in axs:
    ax.relim()
    ax.autoscale_view()

plt.tight_layout()

# --- Update function ---
def update_plot(frame):
    line = ser.readline().decode('utf-8').strip()
    if not line or line.startswith("MPU") or line.startswith("Time"):
        print("Bad line:", line)
        return lines.values()
    try:
        t, ax, ay, az, mag = map(float, line.split(','))
    except ValueError:
        print("Bad line:", line)
        return lines.values()

    # --- Append new data ---
    time_vals.append(t)
    ax_vals.append(ax)
    ay_vals.append(ay)
    az_vals.append(az)
    mag_vals.append(mag)

    # --- Keep rolling window ---
    if len(time_vals) > window_size:
        time_vals.pop(0)
        ax_vals.pop(0)
        ay_vals.pop(0)
        az_vals.pop(0)
        mag_vals.pop(0)

    # --- Convert to arrays ---
    ax_np = np.array(ax_vals)
    ay_np = np.array(ay_vals)
    az_np = np.array(az_vals)
    mag_np = np.array(mag_vals)

    # --- Filter signals (rolling) ---
    ax_filt = apply_bandpass_rolling(ax_np)
    ay_filt = apply_bandpass_rolling(ay_np)
    az_filt = apply_bandpass_rolling(az_np)
    mag_filt = np.sqrt(ax_filt**2 + ay_filt**2 + az_filt**2)

    # --- Thresholding ---
    threshold = np.mean(mag_filt) + 2*np.std(mag_filt)
    crossings = mag_filt > threshold

    # --- Update lines ---
    lines['ax_raw'].set_data(time_vals, ax_np)
    lines['ay_raw'].set_data(time_vals, ay_np)
    lines['az_raw'].set_data(time_vals, az_np)
    lines['ax_filt'].set_data(time_vals, ax_filt)
    lines['ay_filt'].set_data(time_vals, ay_filt)
    lines['az_filt'].set_data(time_vals, az_filt)
    lines['mag_raw'].set_data(time_vals, mag_np)
    lines['mag_filt'].set_data(time_vals, mag_filt)
    lines['threshold'].set_data(time_vals, np.full_like(time_vals, threshold))
    lines['crossings'].set_data(time_vals, crossings.astype(float))

    for ax in axs:
        ax.relim()
        ax.autoscale_view()

    return lines.values()

# --- Animation ---
from matplotlib.animation import FuncAnimation
ani = FuncAnimation(fig, update_plot, interval=50, blit=False, cache_frame_data=False)
plt.show()
