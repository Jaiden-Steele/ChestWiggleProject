import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
import numpy as np
from collections import deque
import time
from matplotlib.animation import FuncAnimation

# ===================== CONFIG =====================
PORT = None  # Set to None for auto-detect, or e.g. 'COM3' or '/dev/ttyUSB0'
BAUDRATE = 115200
WINDOW_SEC = 0.25  # 250 ms window
FS = 100           # Sampling rate (100 Hz from your 10ms interval)
BUFFER_SIZE = int(FS * WINDOW_SEC * 3)  # Extra buffer
# =================================================

# Auto-detect Arduino
def find_arduino():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = p.description.lower()
        if any(keyword in desc for keyword in ['arduino', 'ch340', 'usb serial', 'usb-serial']):
            print(f"Found Arduino at {p.device} ({p.description})")
            return p.device
    return None

port = PORT or find_arduino()
if not port:
    raise SystemExit("Arduino not found! Check connection or set PORT manually.")

print(f"Connecting to {port} @ {BAUDRATE} baud...")
ser = serial.Serial(port, BAUDRATE, timeout=1)
time.sleep(2)  # Important: wait for Arduino reset
ser.flushInput()

# Clear any junk startup lines
print("Flushing startup messages...")
for _ in range(20):
    ser.readline()

# ===================== DATA BUFFERS =====================
time_vals = deque(maxlen=BUFFER_SIZE)
ax_vals   = deque(maxlen=BUFFER_SIZE)
ay_vals   = deque(maxlen=BUFFER_SIZE)
az_vals   = deque(maxlen=BUFFER_SIZE)
mag_vals  = deque(maxlen=BUFFER_SIZE)

# ===================== PLOT SETUP =====================
plt.style.use('dark_background')
fig, axs = plt.subplots(4, 1, figsize=(12, 9))
fig.suptitle('Live MPU6050 Accelerometer - 250ms Sliding Window', fontsize=14, color='white')

# Colors
colors = {'ax': '#ff4444', 'ay': '#44ff44', 'az': '#4444ff'}

# Lines
line_ax, = axs[0].plot([], [], color=colors['ax'], label='Ax', linewidth=1.5)
line_ay, = axs[0].plot([], [], color=colors['ay'], label='Ay', linewidth=1.5)
line_az, = axs[0].plot([], [], color=colors['az'], label='Az', linewidth=1.5)
axs[0].set_ylabel('Accel (g)', fontsize=10)
axs[0].legend(loc='upper right', fontsize=9)
axs[0].grid(True, alpha=0.3)
axs[0].set_ylim(-2, 2)

line_mag_raw, = axs[1].plot([], [], color='white', label='Raw Mag', linewidth=1, alpha=0.5)
line_mag_filt, = axs[1].plot([], [], color='cyan', label='Filtered Mag', linewidth=2)
axs[1].set_ylabel('Magnitude (g)', fontsize=10)
axs[1].legend(loc='upper right', fontsize=9)
axs[1].grid(True, alpha=0.3)
axs[1].set_ylim(0, 2)

# Threshold line
line_thresh = axs[1].axhline(1.5, color='red', linestyle='--', alpha=0.8, linewidth=1.5)

# Event markers
line_events, = axs[2].plot([], [], 'o', color='yellow', markersize=8, label='Shake Detected')
axs[2].set_ylabel('Events', fontsize=10)
axs[2].set_ylim(-0.5, 1.5)
axs[2].set_yticks([0, 1])
axs[2].set_yticklabels(['', 'SHAKE!'])
axs[2].grid(True, alpha=0.3)
axs[2].legend(loc='upper right', fontsize=9)

# Bottom subplot for spacing
axs[3].set_xlabel('Time (ms)', fontsize=10)
axs[3].set_ylabel('')
axs[3].set_yticks([])
axs[3].grid(True, alpha=0.3)
axs[3].set_xlim(-250, 0)

# Share x-axis
for ax in axs:
    ax.set_xlim(-250, 0)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# ===================== ANIMATION UPDATE =====================
last_plot_time = time.time()

def update(frame):
    global line_thresh, last_plot_time

    # Read all available lines
    lines_read = 0
    while lines_read < 50:  # Limit to avoid blocking
        raw = ser.readline()
        if not raw:
            break
        lines_read += 1
        
        try:
            line = raw.decode('utf-8').strip()
        except:
            continue

        # Skip headers/comments
        if not line or line.startswith(('MPU', 'Time', '#')):
            continue

        parts = line.split(',')
        if len(parts) < 5:
            continue

        try:
            t_ms, ax_raw, ay_raw, az_raw, mag_raw = map(float, parts[:5])
        except:
            continue

        # Convert to g (MPU6050 default: ±2g range, 16384 LSB/g)
        ax = ax_raw / 16384.0
        ay = ay_raw / 16384.0
        az = az_raw / 16384.0
        # Arduino sends raw magnitude - need to convert it too
        mag = mag_raw / 16384.0

        # Append to buffers
        time_vals.append(t_ms)
        ax_vals.append(ax)
        ay_vals.append(ay)
        az_vals.append(az)
        mag_vals.append(mag)

    # Update plots only if we have data
    if len(time_vals) > 10:
        t = np.array(time_vals)
        
        # Get latest time and create sliding window
        t_latest = t[-1]
        t_rel = t - t_latest  # Relative to latest (will be negative)

        ax_arr = np.array(ax_vals)
        ay_arr = np.array(ay_vals)
        az_arr = np.array(az_vals)
        mag_arr = np.array(mag_vals)

        # Filter magnitude with moving average
        window_size = min(10, len(mag_arr) // 2)
        if len(mag_arr) >= window_size:
            mag_filt = np.convolve(mag_arr, np.ones(window_size)/window_size, mode='same')
        else:
            mag_filt = mag_arr

        # Update lines
        line_ax.set_data(t_rel, ax_arr)
        line_ay.set_data(t_rel, ay_arr)
        line_az.set_data(t_rel, az_arr)
        line_mag_raw.set_data(t_rel, mag_arr)
        line_mag_filt.set_data(t_rel, mag_filt)

        # Dynamic threshold based on recent data
        if len(mag_filt) > 20:
            recent_mag = mag_filt[-20:]
            thresh = np.mean(recent_mag) + 2.0 * np.std(recent_mag)
            thresh = max(thresh, 1.2)  # Minimum threshold
            line_thresh.set_ydata([thresh, thresh])

            # Detect shakes (magnitude spikes)
            if np.any(mag_filt[-5:] > thresh):
                line_events.set_data([t_rel[-1]], [1])
            else:
                line_events.set_data([], [])

        # Set consistent X limits (last 250ms)
        for ax in axs:
            ax.set_xlim(-250, 0)

    return line_ax, line_ay, line_az, line_mag_raw, line_mag_filt, line_events

# ===================== START ANIMATION =====================
ani = FuncAnimation(fig, update, interval=20, blit=False, cache_frame_data=False, save_count=100)
plt.show()

print("Plot closed. Goodbye!")
ser.close()


