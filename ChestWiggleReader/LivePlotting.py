import serial
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, lfilter
from collections import deque
from matplotlib.animation import FuncAnimation

# --- Serial setup ---
ser = serial.Serial('COM3', 115200, timeout=1)  # adjust COM port

# --- Plot setup ---
plt.style.use('ggplot')
fig, axs = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
window_size = 400  # number of samples in sliding window

# --- Buffers using deque for fast rolling ---
time_vals = deque(maxlen=window_size)
ax_vals = deque(maxlen=window_size)
ay_vals = deque(maxlen=window_size)
az_vals = deque(maxlen=window_size)
mag_vals = deque(maxlen=window_size)

# --- Band-pass filter ---
def make_bandpass(lowcut=5, highcut=15, fs=100, order=4):
    nyq = 0.5 * fs
    low, high = lowcut/nyq, highcut/nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

b, a = make_bandpass()

def apply_bandpass_rolling(data):
    if len(data) < 25:
        return np.zeros_like(data)
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

plt.tight_layout()

# --- Update function ---
def update_plot(frame):
    # Read a line from serial
    line_bytes = ser.readline()
    try:
        line = line_bytes.decode('utf-8').strip()
    except UnicodeDecodeError:
        return lines.values()  # skip bad lines

    if not line or line.startswith("MPU") or line.startswith("Time"):
        return lines.values()

    try:
        t, ax, ay, az, mag = map(float, line.split(','))
    except ValueError:
        return lines.values()

    # --- Append new data to deque (old data auto-removed) ---
    time_vals.append(t)
    ax_vals.append(ax)
    ay_vals.append(ay)
    az_vals.append(az)
    mag_vals.append(mag)

    # --- Remove old data beyond 1000 ms window ---
    window_ms = 1000
    while time_vals and (t - time_vals[0] > window_ms):
        time_vals.popleft()
        ax_vals.popleft()
        ay_vals.popleft()
        az_vals.popleft()
        mag_vals.popleft()


    # --- Convert to numpy arrays ---
    ax_np = np.array(ax_vals)
    ay_np = np.array(ay_vals)
    az_np = np.array(az_vals)
    mag_np = np.array(mag_vals)
    t_np = np.array(time_vals)

    # --- Apply bandpass filter ---
    ax_filt = apply_bandpass_rolling(ax_np)
    ay_filt = apply_bandpass_rolling(ay_np)
    az_filt = apply_bandpass_rolling(az_np)
    mag_filt = np.sqrt(ax_filt**2 + ay_filt**2 + az_filt**2)

    # --- Threshold crossings ---
    threshold = np.mean(mag_filt) + 2*np.std(mag_filt)
    crossings = mag_filt > threshold

    # --- Update lines ---
    t_rel = t_np - t_np[0]  # make x-axis start at 0
    lines['ax_raw'].set_data(t_rel, ax_np)
    lines['ay_raw'].set_data(t_rel, ay_np)
    lines['az_raw'].set_data(t_rel, az_np)
    lines['ax_filt'].set_data(t_rel, ax_filt)
    lines['ay_filt'].set_data(t_rel, ay_filt)
    lines['az_filt'].set_data(t_rel, az_filt)
    lines['mag_raw'].set_data(t_rel, mag_np)
    lines['mag_filt'].set_data(t_rel, mag_filt)
    lines['threshold'].set_data(t_rel, np.full_like(t_rel, threshold))
    lines['crossings'].set_data(t_rel, crossings.astype(float))

    # --- Sliding x-axis ---
    for ax in axs:
        ax.set_xlim(0, t_rel[-1])
        ax.autoscale_view(scalex=False, scaley=True)

    return lines.values()

# --- Animation ---
ani = FuncAnimation(fig, update_plot, interval=50, blit=False)
plt.show()

