import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle
from scipy import signal
import serial
import serial.tools.list_ports
from collections import deque
import time
# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# System States
STATE_NORMAL = 0
STATE_LOW_SIGNAL = 1
STATE_FAULT = 2

STATE_NAMES = {STATE_NORMAL: "NORMAL", STATE_LOW_SIGNAL: "LOW SIGNAL", STATE_FAULT: "FAULT"}
STATE_COLORS = {STATE_NORMAL: 'lightgreen', STATE_LOW_SIGNAL: 'yellow', STATE_FAULT: 'red'}

class HFOVMonitor:
    def __init__(self, port=None, baudrate=115200):
        self.fs = 100
        self.serial_port = None
        
        # Waveform buffers (2 seconds)
        self.wave_size = 200
        self.wave_time = deque(maxlen=self.wave_size)
        self.wave_ax = deque(maxlen=self.wave_size)
        self.wave_ay = deque(maxlen=self.wave_size)
        self.wave_az = deque(maxlen=self.wave_size)
        self.wave_mag = deque(maxlen=self.wave_size)
        self.sample_count = 0
        
        # Clinical metrics buffers (10 seconds at 5 Hz = 50 points)
        self.clinical_size = 50
        self.clin_time = deque(maxlen=self.clinical_size)
        self.clin_freq = deque(maxlen=self.clinical_size)
        self.clin_amp = deque(maxlen=self.clinical_size)
        self.clin_snr = deque(maxlen=self.clinical_size)
        
        # Current values
        self.current_freq = 0
        self.current_amp = 0
        self.current_snr = 0
        self.current_state = STATE_NORMAL
        
        # Timing
        self.start_time = time.time()
        self.last_analysis = time.time()
        self.analysis_interval = 0.2  # 5 Hz
        self.last_data_time = time.time()
        
        # Bandpass filter (5-15 Hz)
        self.sos = signal.butter(4, [5, 15], btype='band', fs=self.fs, output='sos')
        
        # Connect
        if port:
            self.connect_serial(port, baudrate)
        else:
            self.auto_detect_arduino(baudrate)
        
        self.setup_plot()
        self.frame_count = 0
        
    def auto_detect_arduino(self, baudrate):
        print("\n" + "="*70)
        print("HFOV MONITOR - Searching for Arduino...")
        print("="*70)
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            raise ConnectionError("No serial ports found")
        
        print("\nAvailable ports:")
        for i, port in enumerate(ports):
            print(f"  {i+1}. {port.device} - {port.description}")
        
        arduino_ports = [p for p in ports if 'Arduino' in p.description or 
                        'CH340' in p.description or 'USB' in p.description]
        
        if arduino_ports:
            self.connect_serial(arduino_ports[0].device, baudrate)
        else:
            for port in ports:
                try:
                    self.connect_serial(port.device, baudrate)
                    return
                except:
                    continue
            raise ConnectionError("Failed to connect")
    
    def connect_serial(self, port, baudrate):
        print(f"\n> Connecting to {port}...")
        
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=0.01)
        except Exception as e:
            raise ConnectionError(f"Could not open port: {e}")
        
        print(f"  Waiting for Arduino boot (7 sec)...")
        time.sleep(7)
        self.serial_port.flushInput()
        
        # Wait for valid data
        start = time.time()
        while (time.time() - start) < 5:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8').strip()
                    if line.startswith('#'):
                        print(f"  Arduino: {line}")
                        continue
                    parts = line.split(',')
                    if len(parts) == 3:
                        print(f"  Receiving data: {line[:30]}...")
                        print(f"  Connected!\n")
                        return
            except:
                pass
            time.sleep(0.05)
        
        raise ConnectionError("No valid data received")
    
    def read_data(self):
        """Read ax,ay,az from Arduino"""
        if not self.serial_port or not self.serial_port.is_open:
            return None
        
        try:
            if self.serial_port.in_waiting:
                line = self.serial_port.readline().decode('utf-8').strip()
                if not line or line.startswith('#'):
                    return None
                parts = line.split(',')
                if len(parts) == 3:
                    return float(parts[0]), float(parts[1]), float(parts[2])
        except:
            pass
        return None
    
    def analyze_signal(self):
        """Compute frequency, amplitude, SNR from waveform buffer"""
        if len(self.wave_mag) < 100:
            return
        
        # Get data
        mag = np.array(list(self.wave_mag))
        
        # Apply bandpass filter
        mag_filt = signal.sosfiltfilt(self.sos, mag)
        
        # Frequency (zero-crossing)
        crossings = 0
        for i in range(1, len(mag_filt)):
            if (mag_filt[i-1] >= 0 and mag_filt[i] < 0) or (mag_filt[i-1] < 0 and mag_filt[i] >= 0):
                crossings += 1
        freq = (crossings / 2.0) * self.fs / len(mag_filt)
        
        # Amplitude
        amp = np.max(np.abs(mag_filt)) * 1000  # millig
        
        # SNR
        signal_power = np.mean(mag_filt**2)
        noise = mag - mag_filt
        noise_power = np.mean(noise**2)
        snr = 10 * np.log10(signal_power / (noise_power + 1e-10)) if noise_power > 0 else 40
        
        return freq, amp, max(0, snr)
    
    def setup_plot(self):
        self.fig = plt.figure(figsize=(18, 10))
        self.fig.suptitle('HFOV Clinical Monitor - Live Waveform', 
                         fontsize=18, fontweight='bold', y=0.97)
        
        gs = self.fig.add_gridspec(4, 3, hspace=0.4, wspace=0.3, 
                                   top=0.93, bottom=0.06, left=0.05, right=0.98)
        
        # Alert banner
        self.ax_alert = self.fig.add_subplot(gs[0, :])
        self.ax_alert.axis('off')
        self.alert_bg = Rectangle((0, 0), 1, 1, transform=self.ax_alert.transAxes,
                                  facecolor='lightgreen', alpha=0.3)
        self.ax_alert.add_patch(self.alert_bg)
        self.alert_text = self.ax_alert.text(0.5, 0.5, '', ha='center', va='center',
                                            fontsize=16, fontweight='bold')
        
        # WAVEFORM
        self.ax_wave = self.fig.add_subplot(gs[1, :])
        self.ax_wave.set_title('Real-Time Chest Oscillation (2 sec window)', 
                              fontsize=13, fontweight='bold')
        self.ax_wave.set_xlabel('Time (seconds)')
        self.ax_wave.set_ylabel('Acceleration (g)')
        self.ax_wave.grid(True, alpha=0.3)
        self.ax_wave.set_xlim(0, 2)
        self.ax_wave.set_ylim(-0.15, 0.15)
        self.line_mag = self.ax_wave.plot([], [], 'b-', linewidth=2.5, label='Magnitude')[0]
        self.line_z = self.ax_wave.plot([], [], 'g-', linewidth=1.5, alpha=0.6, label='Z-axis')[0]
        self.ax_wave.legend(loc='upper right')
        self.wave_annot = self.ax_wave.text(0.02, 0.98, '', transform=self.ax_wave.transAxes,
                                           va='top', fontsize=11,
                                           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # CURRENT VALUES
        self.ax_curr = self.fig.add_subplot(gs[2, 0])
        self.ax_curr.axis('off')
        self.ax_curr.set_title('Current CWF', fontsize=12, fontweight='bold')
        self.curr_text = self.ax_curr.text(0.5, 0.5, '', ha='center', va='center',
                                          fontsize=11, family='monospace',
                                          bbox=dict(boxstyle='round', facecolor='white', 
                                                   edgecolor='gray', linewidth=2))
        
        # SPECTRUM
        self.ax_spec = self.fig.add_subplot(gs[2, 1])
        self.ax_spec.set_title('Live Spectrum', fontsize=12, fontweight='bold')
        self.ax_spec.set_xlabel('Frequency (Hz)')
        self.ax_spec.set_ylabel('Power (dB)')
        self.ax_spec.grid(True, alpha=0.3)
        self.ax_spec.set_xlim(0, 20)
        self.ax_spec.set_ylim(-60, 0)
        self.line_spec = self.ax_spec.plot([], [], 'b-', linewidth=2)[0]
        self.ax_spec.axvspan(5, 15, alpha=0.1, color='green')
        
        # STATUS
        self.ax_stat = self.fig.add_subplot(gs[2, 2])
        self.ax_stat.axis('off')
        self.ax_stat.set_title('System Status', fontsize=12, fontweight='bold')
        self.stat_text = self.ax_stat.text(0.5, 0.5, '', ha='center', va='center',
                                          fontsize=10, family='monospace',
                                          bbox=dict(boxstyle='round', facecolor='white', 
                                                   edgecolor='gray', linewidth=2))
        
        # TREND PLOTS
        self.ax_freq = self.fig.add_subplot(gs[3, 0])
        self.ax_freq.set_title('Frequency (10s)', fontsize=11, fontweight='bold')
        self.ax_freq.set_xlabel('Seconds ago')
        self.ax_freq.set_ylabel('Hz')
        self.ax_freq.grid(True, alpha=0.3)
        self.ax_freq.set_xlim(10, 0)
        self.ax_freq.set_ylim(0, 20)
        self.line_freq = self.ax_freq.plot([], [], 'b-', linewidth=1.5, marker='o', markersize=3)[0]
        self.ax_freq.axhspan(5, 15, alpha=0.1, color='green')
        
        self.ax_amp = self.fig.add_subplot(gs[3, 1])
        self.ax_amp.set_title('Amplitude (10s)', fontsize=11, fontweight='bold')
        self.ax_amp.set_xlabel('Seconds ago')
        self.ax_amp.set_ylabel('mg')
        self.ax_amp.grid(True, alpha=0.3)
        self.ax_amp.set_xlim(10, 0)
        self.ax_amp.set_ylim(0, 100)
        self.line_amp = self.ax_amp.plot([], [], 'm-', linewidth=1.5, marker='o', markersize=3)[0]
        
        self.ax_snr = self.fig.add_subplot(gs[3, 2])
        self.ax_snr.set_title('SNR (10s)', fontsize=11, fontweight='bold')
        self.ax_snr.set_xlabel('Seconds ago')
        self.ax_snr.set_ylabel('dB')
        self.ax_snr.grid(True, alpha=0.3)
        self.ax_snr.set_xlim(10, 0)
        self.ax_snr.set_ylim(0, 40)
        self.line_snr = self.ax_snr.plot([], [], 'g-', linewidth=1.5, marker='o', markersize=3)[0]
        self.ax_snr.axhline(y=10, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
    
    def update_plot(self, frame):
        current_time = time.time()
        
        # Read up to 30 samples per frame
        for _ in range(30):
            data = self.read_data()
            if data:
                ax, ay, az = data
                t = self.sample_count / self.fs
                mag = np.sqrt(ax**2 + ay**2 + az**2)
                
                self.wave_time.append(t)
                self.wave_ax.append(ax)
                self.wave_ay.append(ay)
                self.wave_az.append(az)
                self.wave_mag.append(mag)
                self.sample_count += 1
                self.last_data_time = current_time
        
        # Analyze every 200ms (5 Hz)
        if current_time - self.last_analysis > self.analysis_interval:
            self.last_analysis = current_time
            result = self.analyze_signal()
            if result:
                freq, amp, snr = result
                self.current_freq = freq
                self.current_amp = amp
                self.current_snr = snr
                
                elapsed = current_time - self.start_time
                self.clin_time.append(elapsed)
                self.clin_freq.append(freq)
                self.clin_amp.append(amp)
                self.clin_snr.append(snr)
                
                # Update state
                if snr < 10:
                    self.current_state = STATE_LOW_SIGNAL
                else:
                    self.current_state = STATE_NORMAL
        
        # Check timeout
        if current_time - self.last_data_time > 3:
            self.current_state = STATE_FAULT
        
        # Update displays
        self.update_alert()
        self.update_waveform()
        self.update_current()
        self.update_spectrum()
        self.update_status()
        self.update_trends()
        
        self.frame_count += 1
    
    def update_alert(self):
        state = self.current_state
        if state == STATE_NORMAL:
            self.alert_bg.set_facecolor('lightgreen')
            self.alert_text.set_text('* SYSTEM NORMAL - Monitoring Active')
            self.alert_text.set_color('darkgreen')
        elif state == STATE_LOW_SIGNAL:
            self.alert_bg.set_facecolor('yellow')
            self.alert_text.set_text('! WARNING: LOW SIGNAL QUALITY')
            self.alert_text.set_color('orange')
        else:
            self.alert_bg.set_facecolor('red')
            self.alert_text.set_text('!! FAULT: NO DATA !!')
            self.alert_text.set_color('white')
    
    def update_waveform(self):
        if len(self.wave_time) < 2:
            return
        
        t = np.array(list(self.wave_time))
        mag = np.array(list(self.wave_mag))
        z = np.array(list(self.wave_az))
        
        # Show last 2 seconds
        t_offset = t[-1] - 2
        t_disp = t - t_offset
        mask = (t_disp >= 0) & (t_disp <= 2)
        
        if np.sum(mask) > 0:
            self.line_mag.set_data(t_disp[mask], mag[mask])
            self.line_z.set_data(t_disp[mask], z[mask])
            
            ymax = max(0.15, np.max(np.abs(mag[mask])) * 1.3)
            self.ax_wave.set_ylim(-ymax, ymax)
            
            self.wave_annot.set_text(f'Samples: {len(self.wave_time)}\nFreq: {self.current_freq:.1f} Hz')
    
    def update_current(self):
        text = f"""
+------------------------+
|  CHEST WIGGLE FACTOR   |
+------------------------+
|  Freq: {self.current_freq:5.1f} Hz    |
|  Amp:  {self.current_amp:5.1f} mg    |
|  SNR:  {self.current_snr:5.1f} dB    |
+------------------------+
        """
        self.curr_text.set_text(text)
        
        color = 'green' if self.current_state == STATE_NORMAL else 'red'
        self.curr_text.get_bbox_patch().set_edgecolor(color)
        self.curr_text.get_bbox_patch().set_linewidth(3)
    
    def update_spectrum(self):
        if len(self.wave_mag) < 64:
            return
        
        data = np.array(list(self.wave_mag))
        try:
            freqs, psd = signal.welch(data, fs=self.fs, nperseg=min(64, len(data)))
            psd_db = 10 * np.log10(psd + 1e-12)
            self.line_spec.set_data(freqs, psd_db)
            
            ymin = max(-80, np.min(psd_db) - 5)
            ymax = min(20, np.max(psd_db) + 5)
            self.ax_spec.set_ylim(ymin, ymax)
        except:
            pass
    
    def update_status(self):
        elapsed = time.time() - self.start_time
        text = f"""
+------------------+
|  Status          |
+------------------+
|  {STATE_NAMES[self.current_state]:<15s} |
|  Runtime: {elapsed:5.0f}s  |
|  Samples: {self.sample_count:<6d} |
+------------------+
        """
        self.stat_text.set_text(text)
        self.stat_text.get_bbox_patch().set_facecolor(STATE_COLORS[self.current_state])
        self.stat_text.get_bbox_patch().set_alpha(0.4)
    
    def update_trends(self):
        if len(self.clin_time) == 0:
            return
        
        current_t = self.clin_time[-1]
        t_ago = [current_t - t for t in self.clin_time]
        t_ago.reverse()
        
        freq_data = list(self.clin_freq); freq_data.reverse()
        amp_data = list(self.clin_amp); amp_data.reverse()
        snr_data = list(self.clin_snr); snr_data.reverse()
        
        self.line_freq.set_data(t_ago, freq_data)
        self.line_amp.set_data(t_ago, amp_data)
        self.line_snr.set_data(t_ago, snr_data)
        
        if len(freq_data) > 0:
            self.ax_freq.set_ylim(0, max(20, max(freq_data) * 1.2))
            self.ax_amp.set_ylim(0, max(100, max(amp_data) * 1.2))
            self.ax_snr.set_ylim(0, max(40, max(snr_data) * 1.2))
    
    def run(self):
        print("\n" + "="*70)
        print("HFOV MONITOR - Streaming at 100 Hz")
        print("="*70)
        print("\nFeatures:")
        print("  - Real-time waveform (100 Hz)")
        print("  - Clinical metrics (5 Hz)")
        print("  - Live spectrum")
        print("  - 10-second trends")
        print("\nPress Q to quit")
        print("="*70 + "\n")
        
        self.fig.canvas.mpl_connect('key_press_event', lambda e: plt.close() if e.key == 'q' else None)
        self.anim = FuncAnimation(self.fig, self.update_plot, interval=33, blit=False)
        plt.show()
        
        if self.serial_port:
            self.serial_port.close()

if __name__ == "__main__":
    try:
        monitor = HFOVMonitor()
        monitor.run()
    except ConnectionError as e:
        print(f"\nERROR: {e}")
        exit(1)
    except KeyboardInterrupt:
        print("\nStopped")
        exit(0)