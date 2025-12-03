import sys
import time
from collections import deque

import numpy as np
from scipy import signal

# Serial is optional — if not present the monitor will raise on connect
import serial
import serial.tools.list_ports

from PyQt5 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# -------------------------
# Constants / States
# -------------------------
STATE_NORMAL = 0
STATE_LOW_SIGNAL = 1
STATE_FAULT = 2

STATE_NAMES = {STATE_NORMAL: "NORMAL", STATE_LOW_SIGNAL: "LOW SIGNAL", STATE_FAULT: "FAULT"}
STATE_COLORS = {STATE_NORMAL: '#4CAF50', STATE_LOW_SIGNAL: '#FFC107', STATE_FAULT: '#F44336'}

# -------------------------
# Backend: acquisition + analysis
# -------------------------
class HFOVBackend:
    def __init__(self, port=None, baudrate=115200, fs=100):
        self.fs = fs
        self.serial_port = None

        # Buffers (2 sec @ 100 Hz)
        self.wave_size = 200
        self.wave_time = deque(maxlen=self.wave_size)
        self.wave_ax = deque(maxlen=self.wave_size)
        self.wave_ay = deque(maxlen=self.wave_size)
        self.wave_az = deque(maxlen=self.wave_size)
        self.wave_mag = deque(maxlen=self.wave_size)
        self.sample_count = 0

        # Clinical metrics (10s @ 5 Hz ≈ 50 points)
        self.clinical_size = 50
        self.clin_time = deque(maxlen=self.clinical_size)
        self.clin_freq = deque(maxlen=self.clinical_size)
        self.clin_amp = deque(maxlen=self.clinical_size)
        self.clin_snr = deque(maxlen=self.clinical_size)

        # Current metrics
        self.current_freq = 0.0
        self.current_amp = 0.0
        self.current_snr = -99.0
        self.current_state = STATE_NORMAL

        # Timing
        self.start_time = time.time()
        self.last_analysis = time.time()
        self.analysis_interval = 0.2  # 5 Hz
        self.last_data_time = time.time()

        # SNR threshold per specification (15 dB)
        self.snr_threshold_db = 15.0

        # Bandpass filter (5-15 Hz)
        self.sos = signal.butter(4, [5, 15], btype='band', fs=self.fs, output='sos')

        # Connect serial (auto-detect if port not provided)
        if port:
            self.connect_serial(port, baudrate)
        else:
            self.auto_detect_arduino(baudrate)

    # -------------------------
    # Serial helpers
    # -------------------------
    def auto_detect_arduino(self, baudrate):
        ports = serial.tools.list_ports.comports()
        if not ports:
            raise ConnectionError("No serial ports found")
        arduino_ports = [p for p in ports if 'Arduino' in p.description or 'CH340' in p.description or 'USB' in p.description]
        if arduino_ports:
            self.connect_serial(arduino_ports[0].device, baudrate)
        else:
            # try first available
            self.connect_serial(ports[0].device, baudrate)

    def connect_serial(self, port, baudrate):
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=0.01)
        except Exception as e:
            raise ConnectionError(f"Could not open port {port}: {e}")
        # give device time to boot
        time.sleep(2)
        self.serial_port.flushInput()
        # quick sanity read
        start = time.time()
        while time.time() - start < 3:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(',')
                    if len(parts) == 3:
                        return
            except Exception:
                pass

    def read_data(self):
        """Read ax,ay,az from Arduino (non-blocking). Returns tuple or None."""
        if not self.serial_port or not self.serial_port.is_open:
            return None
        try:
            if self.serial_port.in_waiting:
                line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                if not line or line.startswith('#'):
                    return None
                parts = line.split(',')
                if len(parts) == 3:
                    return float(parts[0]), float(parts[1]), float(parts[2])
        except Exception:
            # swallow parse errors — return None so acquisition continues
            return None
        return None

    # -------------------------
    # Analysis (FFT-based + fallback; NaN/clip checks)
    # -------------------------
    def analyze_signal(self):
        if len(self.wave_mag) < 120:  # need ~1.2 s of data
            return None

        ax = np.array(self.wave_ax, dtype=float)
        ay = np.array(self.wave_ay, dtype=float)
        az = np.array(self.wave_az, dtype=float)

        # sanity: NaNs
        if np.any(np.isnan(ax)) or np.any(np.isnan(ay)) or np.any(np.isnan(az)):
            return 0.0, 0.0, -30.0

        # clip spikes
        ax = np.clip(ax, -4, 4)
        ay = np.clip(ay, -4, 4)
        az = np.clip(az, -4, 4)

        # remove DC and compute magnitude
        ax -= np.mean(ax)
        ay -= np.mean(ay)
        az -= np.mean(az)
        mag = np.sqrt(ax ** 2 + ay ** 2 + az ** 2)

        raw_amp = np.std(mag) * 1000.0  # in mg

        # filter
        try:
            mag_filt = signal.sosfiltfilt(self.sos, mag)
        except Exception:
            return 0.0, raw_amp, -30.0

        amp = np.std(mag_filt) * 1000.0

        # FFT-based freq estimation (recommended)
        freq_fft = 0.0
        if raw_amp > 2.0:
            N = len(mag_filt)
            window = np.hanning(N)
            yf = np.abs(np.fft.rfft(mag_filt * window))
            xf = np.fft.rfftfreq(N, 1.0 / self.fs)
            mask = (xf >= 5) & (xf <= 15)
            if np.sum(mask) > 3:
                yf_band = yf[mask]
                xf_band = xf[mask]
                peak_idx = np.argmax(yf_band)
                peak = yf_band[peak_idx]
                avg_power = np.mean(yf_band) + 1e-12
                if peak > 2.0 * avg_power and peak > 0:
                    freq_fft = xf_band[peak_idx]

        # fallback zero-crossing
        if freq_fft == 0.0:
            crossings = 0
            for i in range(1, len(mag_filt)):
                if (mag_filt[i - 1] >= 0 and mag_filt[i] < 0) or (mag_filt[i - 1] < 0 and mag_filt[i] >= 0):
                    crossings += 1
            freq = (crossings / 2.0) * self.fs / len(mag_filt)
        else:
            freq = float(freq_fft)

        # SNR
        signal_power = np.var(mag_filt)
        total_power = np.var(mag)
        noise_power = total_power - signal_power
        if noise_power <= 0:
            noise_power = 1e-12

        if signal_power < 1e-12:
            snr = -30.0
        else:
            snr = 10.0 * np.log10(signal_power / noise_power)
            snr = float(np.clip(snr, -30.0, 40.0))

        return float(freq), float(amp), float(snr)

    # -------------------------
    # update() called by GUI timer
    # -------------------------
    def update(self):
        current_time = time.time()

        # read up to 30 samples per tick (non-blocking reads)
        for _ in range(30):
            data = self.read_data()
            if data:
                ax, ay, az = data
                t = self.sample_count / float(self.fs)
                mag = float(np.sqrt(ax * ax + ay * ay + az * az))
                self.wave_time.append(t)
                self.wave_ax.append(ax)
                self.wave_ay.append(ay)
                self.wave_az.append(az)
                self.wave_mag.append(mag)
                self.sample_count += 1
                self.last_data_time = current_time

        # analysis at 5 Hz
        if (current_time - self.last_analysis) >= self.analysis_interval:
            self.last_analysis = current_time
            res = self.analyze_signal()
            if res:
                freq, amp, snr = res
                self.current_freq = freq
                self.current_amp = amp
                self.current_snr = snr

                elapsed = current_time - self.start_time
                self.clin_time.append(elapsed)
                self.clin_freq.append(freq)
                self.clin_amp.append(amp)
                self.clin_snr.append(snr)

                # State assignment using SNR threshold (15 dB)
                if snr < self.snr_threshold_db:
                    self.current_state = STATE_LOW_SIGNAL
                else:
                    self.current_state = STATE_NORMAL

        # timeout -> FAULT
        if (current_time - self.last_data_time) > 3.0:
            self.current_state = STATE_FAULT

# -------------------------
# GUI: PyQt5 application with dark mode
# -------------------------
class HFOVWindow(QtWidgets.QMainWindow):
    def __init__(self, backend: HFOVBackend):
        super().__init__()
        self.backend = backend
        self.setWindowTitle("HFOV Clinical Monitor - Dark Mode")
        self.setGeometry(80, 60, 1600, 900)
        
        # Dark mode stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)

        # Main container
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Alert banner ---
        self.alert_label = QtWidgets.QLabel()
        self.alert_label.setFixedHeight(80)
        self.alert_label.setAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont("SansSerif", 22, QtGui.QFont.Bold)
        self.alert_label.setFont(font)
        main_layout.addWidget(self.alert_label)

        # --- Top row: waveform (left, 70%) and spectrum (right, 30%) ---
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(10)
        main_layout.addLayout(top_row, stretch=5)

        # Waveform canvas
        self.wave_canvas = FigureCanvas(Figure(figsize=(6, 3), facecolor='#1e1e1e'))
        self.wave_ax = self.wave_canvas.figure.subplots()
        self.setup_dark_plot(self.wave_ax, "Real-Time Chest Oscillation (2 sec)")
        self.wave_ax.set_xlabel("Time (seconds)", fontsize=18, color='white', fontweight='bold')
        self.wave_ax.set_ylabel("Acceleration (g)", fontsize=18, color='white', fontweight='bold')
        self.wave_ax.set_xlim(0, 2)
        self.line_mag, = self.wave_ax.plot([], [], lw=3.5, label="Magnitude", color='#2196F3')
        self.line_z, = self.wave_ax.plot([], [], lw=2.5, alpha=0.7, label="Z-axis", color='#4CAF50')
        legend = self.wave_ax.legend(loc="upper right", fontsize=16, facecolor='#2e2e2e', edgecolor='white')
        plt.setp(legend.get_texts(), color='white')
        self.wave_ax.tick_params(axis='both', labelsize=14)
        top_row.addWidget(self.wave_canvas, stretch=7)

        # Spectrum canvas
        self.spec_canvas = FigureCanvas(Figure(figsize=(3, 3), facecolor='#1e1e1e'))
        self.spec_ax = self.spec_canvas.figure.subplots()
        self.setup_dark_plot(self.spec_ax, "Live Spectrum")
        self.spec_ax.set_xlabel("Frequency (Hz)", fontsize=18, color='white', fontweight='bold')
        self.spec_ax.set_ylabel("Power (dB)", fontsize=18, color='white', fontweight='bold')
        self.spec_ax.set_xlim(0, 20)
        # Add green HFOV band (5-15 Hz)
        self.spec_ax.axvspan(5, 15, alpha=0.2, color='#4CAF50', label='HFOV Band')
        self.line_spec, = self.spec_ax.plot([], [], lw=3, color='#2196F3')
        legend = self.spec_ax.legend(loc="upper right", fontsize=16, facecolor='#2e2e2e', edgecolor='white')
        plt.setp(legend.get_texts(), color='white')
        self.spec_ax.tick_params(axis='both', labelsize=14)
        top_row.addWidget(self.spec_canvas, stretch=3)

        # --- Middle row: three trend panels ---
        trend_row = QtWidgets.QHBoxLayout()
        trend_row.setSpacing(10)
        main_layout.addLayout(trend_row, stretch=2)

        # Frequency trend
        self.freq_canvas = FigureCanvas(Figure(figsize=(3, 2), facecolor='#1e1e1e'))
        self.freq_ax = self.freq_canvas.figure.subplots()
        self.setup_dark_plot(self.freq_ax, "Frequency (10s)")
        self.freq_ax.set_xlabel("Seconds ago", fontsize=16, color='white', fontweight='bold')
        self.freq_ax.set_ylabel("Hz", fontsize=16, color='white', fontweight='bold')
        self.freq_ax.set_xlim(10, 0)
        self.freq_ax.axhspan(5, 15, alpha=0.15, color='#4CAF50')
        self.line_freq, = self.freq_ax.plot([], [], marker='o', markersize=5, lw=2.5, color='#2196F3')
        self.freq_ax.tick_params(axis='both', labelsize=13)
        trend_row.addWidget(self.freq_canvas)

        # Amplitude trend
        self.amp_canvas = FigureCanvas(Figure(figsize=(3, 2), facecolor='#1e1e1e'))
        self.amp_ax = self.amp_canvas.figure.subplots()
        self.setup_dark_plot(self.amp_ax, "Amplitude (10s)")
        self.amp_ax.set_xlabel("Seconds ago", fontsize=16, color='white', fontweight='bold')
        self.amp_ax.set_ylabel("mg", fontsize=16, color='white', fontweight='bold')
        self.amp_ax.set_xlim(10, 0)
        self.line_amp, = self.amp_ax.plot([], [], marker='o', markersize=5, lw=2.5, color='#E91E63')
        self.amp_ax.tick_params(axis='both', labelsize=13)
        trend_row.addWidget(self.amp_canvas)

        # SNR trend
        self.snr_canvas = FigureCanvas(Figure(figsize=(3, 2), facecolor='#1e1e1e'))
        self.snr_ax = self.snr_canvas.figure.subplots()
        self.setup_dark_plot(self.snr_ax, "SNR (10s)")
        self.snr_ax.set_xlabel("Seconds ago", fontsize=16, color='white', fontweight='bold')
        self.snr_ax.set_ylabel("dB", fontsize=16, color='white', fontweight='bold')
        self.snr_ax.set_xlim(10, 0)
        self.snr_ax.axhline(y=self.backend.snr_threshold_db, color='#F44336', linestyle='--', linewidth=2.5)
        self.line_snr, = self.snr_ax.plot([], [], marker='o', markersize=5, lw=2.5, color='#4CAF50')
        self.snr_ax.tick_params(axis='both', labelsize=13)
        trend_row.addWidget(self.snr_canvas)

        # --- Bottom row: info panels ---
        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.setSpacing(15)
        main_layout.addLayout(bottom_row, stretch=1)

        # Current values panel
        self.current_text = QtWidgets.QLabel()
        self.current_text.setAlignment(QtCore.Qt.AlignCenter)
        self.current_text.setMinimumWidth(400)
        self.current_text.setMinimumHeight(120)
        self.current_text.setMaximumHeight(205)
        self.current_text.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        bottom_row.addWidget(self.current_text, stretch=3)

        # Status panel
        self.status_box = QtWidgets.QLabel()
        self.status_box.setAlignment(QtCore.Qt.AlignCenter)
        self.status_box.setMinimumWidth(300)
        self.status_box.setMinimumHeight(120)
        self.status_box.setMaximumHeight(205)
        self.status_box.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        bottom_row.addWidget(self.status_box, stretch=2)

        # Timer for updates (~30 fps)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start()

        # initial draw
        self.update_all_plots(force=True)

    def setup_dark_plot(self, ax, title):
        """Configure a plot axis for dark mode"""
        ax.set_facecolor('#2e2e2e')
        ax.set_title(title, fontsize=19, fontweight='bold', color='white', pad=12)
        ax.tick_params(colors='white', labelsize=13)
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['right'].set_color('white')
        ax.grid(True, alpha=0.2, color='gray')

    # -------------------------
    # Timer tick: update backend + refresh displays
    # -------------------------
    def on_timer(self):
        try:
            self.backend.update()
        except Exception as e:
            print("Backend update error:", e)
        self.update_all_plots()

    # -------------------------
    # Update each plot/widget
    # -------------------------
    def update_all_plots(self, force=False):
        self.update_alert()
        self.update_waveform(force=force)
        self.update_spectrum(force=force)
        self.update_trends(force=force)
        self.update_current_and_status()

    def update_alert(self):
        state = self.backend.current_state
        text = "[ OK ] SYSTEM NORMAL - Monitoring Active" if state == STATE_NORMAL else ("! WARNING: LOW SIGNAL QUALITY" if state == STATE_LOW_SIGNAL else "!! FAULT: NO DATA !!")
        color = STATE_COLORS[state]
        self.alert_label.setText(text)
        self.alert_label.setStyleSheet(f"""
            background-color: {color}; 
            color: white;
            border-radius: 8px; 
            padding: 12px;
            font-weight: bold;
        """)

    def update_waveform(self, force=False):
        if len(self.backend.wave_time) < 2:
            return
        t = np.array(self.backend.wave_time)
        ax = np.array(self.backend.wave_ax)
        ay = np.array(self.backend.wave_ay)
        az = np.array(self.backend.wave_az)

        ax_ac = ax - np.mean(ax)
        ay_ac = ay - np.mean(ay)
        az_ac = az - np.mean(az)
        mag = np.sqrt(ax_ac ** 2 + ay_ac ** 2 + az_ac ** 2)

        t_offset = t[-1] - 2.0
        t_disp = t - t_offset
        mask = (t_disp >= 0) & (t_disp <= 2.0)

        if np.sum(mask) > 0:
            self.line_mag.set_data(t_disp[mask], mag[mask])
            self.line_z.set_data(t_disp[mask], az_ac[mask])
            ymax = max(0.15, np.max(np.abs(mag[mask])) * 1.3) if np.max(np.abs(mag[mask])) > 0 else 0.15
            self.wave_ax.set_ylim(-ymax, ymax)
            self.wave_canvas.draw_idle()

    def update_spectrum(self, force=False):
        if len(self.backend.wave_mag) < 64:
            return
        data = np.array(self.backend.wave_mag)
        data = data - np.mean(data)
        try:
            freqs, psd = signal.welch(data, fs=self.backend.fs, nperseg=min(64, len(data)))
            psd_db = 10.0 * np.log10(psd + 1e-12)
            self.line_spec.set_data(freqs, psd_db)
            ymin = max(-80, np.min(psd_db) - 5)
            ymax = min(20, np.max(psd_db) + 5)
            self.spec_ax.set_ylim(ymin, ymax)
            self.spec_canvas.draw_idle()
        except Exception:
            pass

    def update_trends(self, force=False):
        if len(self.backend.clin_time) == 0:
            return
        current_t = self.backend.clin_time[-1]
        t_ago = [current_t - t for t in self.backend.clin_time]
        t_ago.reverse()

        freq_data = list(self.backend.clin_freq); freq_data.reverse()
        amp_data = list(self.backend.clin_amp); amp_data.reverse()
        snr_data = list(self.backend.clin_snr); snr_data.reverse()

        self.line_freq.set_data(t_ago, freq_data)
        self.line_amp.set_data(t_ago, amp_data)
        self.line_snr.set_data(t_ago, snr_data)

        if len(freq_data) > 0:
            self.freq_ax.set_ylim(0, max(20, max(freq_data) * 1.2))
            self.amp_ax.set_ylim(0, max(100, max(amp_data) * 1.2))
            snr_min = min(snr_data) if snr_data else -30
            snr_max = max(snr_data) if snr_data else 40
            self.snr_ax.set_ylim(min(-30, snr_min - 5), max(40, snr_max + 5))

        self.freq_canvas.draw_idle()
        self.amp_canvas.draw_idle()
        self.snr_canvas.draw_idle()

    def update_current_and_status(self):
        # --- LEFT: Chest Wiggle Factor ---
        freq = f"{self.backend.current_freq:.1f}"
        amp = f"{self.backend.current_amp:.1f}"
        snr = f"{self.backend.current_snr:.1f}"

        html = f"""
        <div style="text-align:center; padding:15px;">
            <p style="font-size:28px; font-weight:bold; margin-bottom:15px;">CHEST WIGGLE FACTOR</p>
            <p style="font-size:26px; margin:8px 0;"><b>Frequency:</b> {freq} Hz</p>
            <p style="font-size:26px; margin:8px 0;"><b>Amplitude:</b> {amp} mg</p>
            <p style="font-size:26px; margin:8px 0;"><b>SNR:</b> {snr} dB</p>
        </div>
        """

        self.current_text.setText(html)
        self.current_text.setStyleSheet("""
            QLabel {
                border: 2px solid #555;
                border-radius: 8px;
                background: #2e2e2e;
                color: #e0e0e0;
                padding: 15px;
            }
        """)

        # --- RIGHT: System Status ---
        state = self.backend.current_state
        state_name = STATE_NAMES[state]
        elapsed = int(time.time() - self.backend.start_time)
        state_color = STATE_COLORS[state]

        status_html = f"""
        <div style="text-align:center; padding:15px;">
            <p style="font-size:32px; font-weight:bold; margin-bottom:15px; color:{state_color};">{state_name}</p>
            <p style="font-size:24px; margin:8px 0;"><b>Runtime:</b> {elapsed}s</p>
            <p style="font-size:24px; margin:8px 0;"><b>Samples:</b> {self.backend.sample_count}</p>
        </div>
        """

        self.status_box.setText(status_html)
        self.status_box.setStyleSheet(f"""
            QLabel {{
                border: 3px solid {state_color};
                border-radius: 8px;
                background: #2e2e2e;
                color: #e0e0e0;
                padding: 15px;
            }}
        """)

# -------------------------
# Application entry point
# -------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)

    try:
        backend = HFOVBackend(port=None)
    except ConnectionError as e:
        QtWidgets.QMessageBox.critical(None, "Connection Error", str(e))
        return

    window = HFOVWindow(backend)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()