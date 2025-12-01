import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle
from scipy import signal
import serial
import serial.tools.list_ports
from collections import deque
import time
from datetime import datetime

# System States (must match Arduino)
STATE_NORMAL = 0
STATE_LOW_SIGNAL = 1
STATE_SENSOR_FAULT = 2
STATE_SYSTEM_FAULT = 3

STATE_NAMES = {
    STATE_NORMAL: "NORMAL",
    STATE_LOW_SIGNAL: "LOW SIGNAL",
    STATE_SENSOR_FAULT: "SENSOR FAULT",
    STATE_SYSTEM_FAULT: "SYSTEM FAULT"
}

STATE_COLORS = {
    STATE_NORMAL: 'lightgreen',
    STATE_LOW_SIGNAL: 'yellow',
    STATE_SENSOR_FAULT: 'orange',
    STATE_SYSTEM_FAULT: 'red'
}

class HFOVClinicalMonitor:
    def __init__(self, port=None, baudrate=115200):
        # Sampling parameters
        self.fs = 100  # 100 Hz from Arduino
        
        # Serial connection
        self.serial_port = None
        
        # Clinical data buffers (60 seconds of trend data)
        self.trend_size = 60
        self.time_buffer = deque(maxlen=self.trend_size)
        self.freq_buffer = deque(maxlen=self.trend_size)
        self.amp_buffer = deque(maxlen=self.trend_size)
        self.rms_buffer = deque(maxlen=self.trend_size)
        self.snr_buffer = deque(maxlen=self.trend_size)
        self.state_buffer = deque(maxlen=self.trend_size)
        
        # Real-time waveform buffers (3 seconds at 100 Hz)
        self.waveform_size = 300
        self.wave_time_buffer = deque(maxlen=self.waveform_size)
        self.wave_ax_buffer = deque(maxlen=self.waveform_size)
        self.wave_ay_buffer = deque(maxlen=self.waveform_size)
        self.wave_az_buffer = deque(maxlen=self.waveform_size)
        self.wave_mag_buffer = deque(maxlen=self.waveform_size)
        self.wave_sample_count = 0
        
        # Current clinical values
        self.current_freq = 0.0
        self.current_amp = 0.0
        self.current_rms = 0.0
        self.current_snr = 0.0
        self.current_state = STATE_NORMAL
        self.uptime = 0
        
        # Alert tracking
        self.alert_active = False
        self.alert_message = ""
        self.alert_start_time = None
        self.last_data_time = time.time()
        
        # Latency tracking
        self.data_receive_times = deque(maxlen=100)
        self.avg_latency = 0
        
        # Initialize connection
        if port:
            self.connect_serial(port, baudrate)
        else:
            self.auto_detect_arduino(baudrate)
        
        # Setup plot
        self.setup_plot()
        
        self.frame_count = 0
        self.start_time = time.time()
        
    def auto_detect_arduino(self, baudrate):
        """Auto-detect Arduino"""
        print("\n" + "="*70)
        print("HFOV CLINICAL MONITOR - Searching for Arduino...")
        print("="*70)
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            raise ConnectionError("No serial ports found")
        
        print("\nAvailable ports:")
        for i, port in enumerate(ports):
            print(f"  {i+1}. {port.device} - {port.description}")
        
        arduino_ports = [p for p in ports if 'Arduino' in p.description or 
                        'CH340' in p.description or 'USB' in p.description or
                        'Serial' in p.description]
        
        if arduino_ports:
            self.connect_serial(arduino_ports[0].device, baudrate)
        else:
            for port in ports:
                try:
                    self.connect_serial(port.device, baudrate)
                    return
                except:
                    continue
            raise ConnectionError("Failed to connect to Arduino")
    
    def connect_serial(self, port, baudrate):
        """Connect to Arduino"""
        print(f"\n→ Connecting to {port}...")
        
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=0.1)
        except Exception as e:
            raise ConnectionError(f"Could not open port: {e}")
        
        print(f"  Port opened at {baudrate} baud")
        print(f"  Waiting for Arduino boot and calibration (7 sec)...")
        time.sleep(7)
        
        self.serial_port.flushInput()
        print(f"  Reading initial data...")
        
        # Wait for valid clinical data
        start_time = time.time()
        while (time.time() - start_time) < 10:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8').strip()
                    
                    if line.startswith('#'):
                        print(f"  Arduino: {line}")
                        continue
                    
                    # Try to parse clinical data format
                    parts = line.split(',')
                    if len(parts) >= 6 and parts[0] == 'C':
                        freq = float(parts[1])
                        print(f"✓ Receiving clinical data: FREQ={freq:.1f}Hz")
                        print(f"✓ Connection successful!\n")
                        return
                        
            except Exception as e:
                pass
            
            time.sleep(0.05)
        
        self.serial_port.close()
        raise ConnectionError("Arduino not sending valid clinical data")
    
    def read_serial_data(self):
        """Read and parse data from Arduino (handles both waveform and clinical)"""
        if not self.serial_port or not self.serial_port.is_open:
            return None
        
        try:
            if self.serial_port.in_waiting:
                line = self.serial_port.readline().decode('utf-8').strip()
                
                if not line or line.startswith('#'):
                    return None
                
                parts = line.split(',')
                
                # Waveform data: W,ax,ay,az,mag (100 Hz)
                if len(parts) == 5 and parts[0] == 'W':
                    return {
                        'type': 'waveform',
                        'ax': float(parts[1]),
                        'ay': float(parts[2]),
                        'az': float(parts[3]),
                        'mag': float(parts[4]),
                        'timestamp': time.time()
                    }
                
                # Clinical data: C,FREQ,AMP,RMS,SNR,STATE,UPTIME (1 Hz)
                elif len(parts) == 7 and parts[0] == 'C':
                    return {
                        'type': 'clinical',
                        'freq': float(parts[1]),
                        'amp': float(parts[2]),
                        'rms': float(parts[3]),
                        'snr': float(parts[4]),
                        'state': int(parts[5]),
                        'uptime': int(parts[6]),
                        'timestamp': time.time()
                    }
        except:
            pass
        
        return None
    
    def setup_plot(self):
        """Setup clinical interface with waveform"""
        self.fig = plt.figure(figsize=(18, 10))
        self.fig.suptitle('HFOV Clinical Monitor - Chest Wiggle Factor', 
                         fontsize=18, fontweight='bold', y=0.97)
        
        gs = self.fig.add_gridspec(4, 3, hspace=0.4, wspace=0.3, 
                                   top=0.93, bottom=0.06, left=0.05, right=0.98)
        
        # ===== ALERT BANNER =====
        self.ax_alert = self.fig.add_subplot(gs[0, :])
        self.ax_alert.axis('off')
        self.alert_bg = Rectangle((0, 0), 1, 1, transform=self.ax_alert.transAxes,
                                  facecolor='lightgreen', alpha=0.3, zorder=0)
        self.ax_alert.add_patch(self.alert_bg)
        self.alert_text = self.ax_alert.text(0.5, 0.5, '', ha='center', va='center',
                                            fontsize=16, fontweight='bold')
        
        # ===== REAL-TIME WAVEFORM (Large, prominent) =====
        self.ax_waveform = self.fig.add_subplot(gs[1, :])
        self.ax_waveform.set_title('Real-Time Chest Oscillation Waveform (2 sec)', 
                                   fontsize=13, fontweight='bold', pad=10)
        self.ax_waveform.set_xlabel('Time (seconds)', fontsize=10)
        self.ax_waveform.set_ylabel('Acceleration (g)', fontsize=10)
        self.ax_waveform.grid(True, alpha=0.3, linestyle='--')
        self.ax_waveform.set_xlim(0, 2)
        self.ax_waveform.set_ylim(-0.15, 0.15)
        
        self.line_wave_mag = self.ax_waveform.plot([], [], 'b-', linewidth=2, 
                                                   label='Vector Magnitude')[0]
        self.line_wave_z = self.ax_waveform.plot([], [], 'g-', linewidth=1, 
                                                 alpha=0.5, label='Z-axis')[0]
        self.ax_waveform.legend(loc='upper right', fontsize=9)
        
        # ===== CURRENT VALUES (Compact) =====
        self.ax_current = self.fig.add_subplot(gs[2, 0])
        self.ax_current.axis('off')
        self.ax_current.set_title('Current CWF', fontsize=12, fontweight='bold', pad=10)
        self.current_text = self.ax_current.text(0.5, 0.5, '', ha='center', va='center',
                                                fontsize=11, family='monospace',
                                                bbox=dict(boxstyle='round', facecolor='white', 
                                                         alpha=0.9, edgecolor='gray', linewidth=2))
        
        # ===== SYSTEM STATUS =====
        self.ax_status = self.fig.add_subplot(gs[2, 1])
        self.ax_status.axis('off')
        self.ax_status.set_title('System Status', fontsize=12, fontweight='bold', pad=10)
        self.status_text = self.ax_status.text(0.5, 0.5, '', ha='center', va='center',
                                              fontsize=10, family='monospace',
                                              bbox=dict(boxstyle='round', facecolor='white', 
                                                       alpha=0.9, edgecolor='gray', linewidth=2))
        
        # ===== FREQUENCY SPECTRUM =====
        self.ax_spectrum = self.fig.add_subplot(gs[2, 2])
        self.ax_spectrum.set_title('Live Spectrum', fontsize=12, fontweight='bold', pad=10)
        self.ax_spectrum.set_xlabel('Frequency (Hz)', fontsize=9)
        self.ax_spectrum.set_ylabel('Power', fontsize=9)
        self.ax_spectrum.grid(True, alpha=0.3)
        self.ax_spectrum.set_xlim(0, 20)
        self.ax_spectrum.set_ylim(-60, 0)
        self.line_spectrum = self.ax_spectrum.plot([], [], 'b-', linewidth=1.5)[0]
        self.ax_spectrum.axvspan(5, 15, alpha=0.1, color='green')
        
        # ===== FREQUENCY TREND =====
        self.ax_freq = self.fig.add_subplot(gs[3, 0])
        self.ax_freq.set_title('Frequency Trend (10s)', fontsize=11, fontweight='bold')
        self.ax_freq.set_xlabel('Seconds ago', fontsize=9)
        self.ax_freq.set_ylabel('Hz', fontsize=9)
        self.ax_freq.grid(True, alpha=0.3)
        self.ax_freq.set_xlim(10, 0)
        self.ax_freq.set_ylim(0, 20)
        self.line_freq = self.ax_freq.plot([], [], 'b-', linewidth=2, marker='o', markersize=4)[0]
        self.ax_freq.axhspan(5, 15, alpha=0.1, color='green')
        
        # ===== AMPLITUDE TREND =====
        self.ax_amp = self.fig.add_subplot(gs[3, 1])
        self.ax_amp.set_title('Amplitude Trend (10s)', fontsize=11, fontweight='bold')
        self.ax_amp.set_xlabel('Seconds ago', fontsize=9)
        self.ax_amp.set_ylabel('mg', fontsize=9)
        self.ax_amp.grid(True, alpha=0.3)
        self.ax_amp.set_xlim(10, 0)
        self.ax_amp.set_ylim(0, 100)
        self.line_amp = self.ax_amp.plot([], [], 'm-', linewidth=2, marker='o', markersize=4, label='Peak')[0]
        self.line_rms = self.ax_amp.plot([], [], 'c--', linewidth=1.5, marker='s', markersize=3, label='RMS')[0]
        self.ax_amp.legend(loc='upper left', fontsize=8)
        
        # ===== SNR TREND =====
        self.ax_snr = self.fig.add_subplot(gs[3, 2])
        self.ax_snr.set_title('SNR Trend (10s)', fontsize=11, fontweight='bold')
        self.ax_snr.set_xlabel('Seconds ago', fontsize=9)
        self.ax_snr.set_ylabel('dB', fontsize=9)
        self.ax_snr.grid(True, alpha=0.3)
        self.ax_snr.set_xlim(10, 0)
        self.ax_snr.set_ylim(0, 40)
        self.line_snr = self.ax_snr.plot([], [], 'g-', linewidth=2, marker='o', markersize=4)[0]
        self.ax_snr.axhline(y=10, color='red', linestyle='--', linewidth=1.5, alpha=0.7)
    
    def update_plot(self, frame):
        """Update clinical display"""
        current_time = time.time()
        
        # Read multiple samples per frame (catch up with 100 Hz stream)
        for _ in range(30):  # Increased from 20 to 30 for better catchup
            data = self.read_serial_data()
            
            if data:
                if data['type'] == 'waveform':
                    # Real-time waveform data (100 Hz)
                    t = self.wave_sample_count / self.fs
                    self.wave_time_buffer.append(t)
                    self.wave_ax_buffer.append(data['ax'])
                    self.wave_ay_buffer.append(data['ay'])
                    self.wave_az_buffer.append(data['az'])
                    self.wave_mag_buffer.append(data['mag'])
                    self.wave_sample_count += 1
                    
                elif data['type'] == 'clinical':
                    # Clinical metrics (1 Hz)
                    self.current_freq = data['freq']
                    self.current_amp = data['amp']
                    self.current_rms = data['rms']
                    self.current_snr = data['snr']
                    self.current_state = data['state']
                    self.uptime = data['uptime']
                    
                    # Add to trend buffers
                    elapsed = current_time - self.start_time
                    self.time_buffer.append(elapsed)
                    self.freq_buffer.append(self.current_freq)
                    self.amp_buffer.append(self.current_amp)
                    self.rms_buffer.append(self.current_rms)
                    self.snr_buffer.append(self.current_snr)
                    self.state_buffer.append(self.current_state)
                    
                    self.last_data_time = current_time
        
        # Check for data timeout
        if current_time - self.last_data_time > 3:
            self.current_state = STATE_SYSTEM_FAULT
        
        # Update all displays
        self.update_alert_display()
        self.update_current_display()
        self.update_status_display()
        self.update_waveform()
        
        if len(self.time_buffer) > 0:
            self.update_trend_plots()
            
        # Update spectrum less frequently (every 5 frames) for performance
        if self.frame_count % 5 == 0:
            self.update_spectrum()
        
        self.frame_count += 1
    
    def update_alert_display(self):
        """Update alert banner based on system state"""
        if self.current_state == STATE_NORMAL:
            self.alert_bg.set_facecolor('lightgreen')
            self.alert_bg.set_alpha(0.3)
            self.alert_text.set_text('● SYSTEM NORMAL - Monitoring Active')
            self.alert_text.set_color('darkgreen')
            self.alert_text.set_fontsize(16)
            self.alert_active = False
            
        elif self.current_state == STATE_LOW_SIGNAL:
            self.alert_bg.set_facecolor('yellow')
            self.alert_bg.set_alpha(0.5)
            self.alert_text.set_text('⚠ WARNING: LOW SIGNAL QUALITY - Check Sensor Placement')
            self.alert_text.set_color('orange')
            self.alert_text.set_fontsize(18)
            self.alert_active = True
            
        elif self.current_state == STATE_SENSOR_FAULT:
            self.alert_bg.set_facecolor('orange')
            self.alert_bg.set_alpha(0.6)
            self.alert_text.set_text('⚠ SENSOR FAULT - Check Connections')
            self.alert_text.set_color('red')
            self.alert_text.set_fontsize(18)
            self.alert_active = True
            
        elif self.current_state == STATE_SYSTEM_FAULT:
            self.alert_bg.set_facecolor('red')
            self.alert_bg.set_alpha(0.7)
            self.alert_text.set_text('⚠⚠ SYSTEM FAULT - Intervention Required ⚠⚠')
            self.alert_text.set_color('white')
            self.alert_text.set_fontsize(20)
            self.alert_active = True
    
    def update_current_display(self):
        """Update large current values display"""
        text = f"""
┌──────────────────────────────┐
│  CHEST WIGGLE FACTOR         │
├──────────────────────────────┤
│  Freq:  {self.current_freq:5.1f} Hz       │
│  Amp:   {self.current_amp:5.1f} mg       │
│  RMS:   {self.current_rms:5.1f} mg       │
│  SNR:   {self.current_snr:5.1f} dB       │
└──────────────────────────────┘
        """
        self.current_text.set_text(text)
        
        # Change color based on state
        if self.current_state == STATE_NORMAL:
            self.current_text.get_bbox_patch().set_edgecolor('green')
            self.current_text.get_bbox_patch().set_linewidth(3)
        else:
            self.current_text.get_bbox_patch().set_edgecolor('red')
            self.current_text.get_bbox_patch().set_linewidth(4)
    
    def update_status_display(self):
        """Update system status panel"""
        state_name = STATE_NAMES.get(self.current_state, "UNKNOWN")
        
        # Format uptime
        hours = self.uptime // 3600
        minutes = (self.uptime % 3600) // 60
        seconds = self.uptime % 60
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        text = f"""
┌──────────────────────┐
│  System Status       │
├──────────────────────┤
│  State: {state_name:<11s} │
│  Uptime: {uptime_str}    │
│  Samples: {self.wave_sample_count:<8d} │
└──────────────────────┘
        """
        self.status_text.set_text(text)
        
        # Color code by state
        bg_color = STATE_COLORS.get(self.current_state, 'white')
        self.status_text.get_bbox_patch().set_facecolor(bg_color)
        self.status_text.get_bbox_patch().set_alpha(0.4)
    
    def update_waveform(self):
        """Update real-time waveform display"""
        if len(self.wave_time_buffer) < 2:
            return
        
        # Get last 2 seconds of data
        time_array = np.array(list(self.wave_time_buffer))
        mag_array = np.array(list(self.wave_mag_buffer))
        z_array = np.array(list(self.wave_az_buffer))
        
        # Shift time to show last 2 seconds
        if len(time_array) > 0:
            time_offset = time_array[-1] - 2
            time_display = time_array - time_offset
            
            self.line_wave_mag.set_data(time_display, mag_array)
            self.line_wave_z.set_data(time_display, z_array)
            
            # Auto-scale Y axis if needed
            if len(mag_array) > 10:
                ymax = max(0.15, np.max(np.abs(mag_array)) * 1.3)
                self.ax_waveform.set_ylim(-ymax, ymax)
    
    def update_spectrum(self):
        """Update frequency spectrum from waveform data"""
        if len(self.wave_mag_buffer) < 100:
            return
        
        # Compute FFT on recent waveform data
        data = np.array(list(self.wave_mag_buffer))[-256:]
        
        freqs, psd = signal.welch(data, fs=self.fs, nperseg=min(128, len(data)))
        psd_db = 10 * np.log10(psd + 1e-10)
        
        self.line_spectrum.set_data(freqs, psd_db)
        
        # Auto-scale
        if len(psd_db) > 0:
            self.ax_spectrum.set_ylim(np.min(psd_db) - 5, np.max(psd_db) + 5)
    
    def update_trend_plots(self):
        """Update trend line plots"""
        # Create time axis (seconds ago)
        current_t = self.time_buffer[-1]
        time_ago = [current_t - t for t in self.time_buffer]
        time_ago.reverse()
        
        # Reverse data for plotting (most recent on right)
        freq_data = list(self.freq_buffer)
        freq_data.reverse()
        amp_data = list(self.amp_buffer)
        amp_data.reverse()
        rms_data = list(self.rms_buffer)
        rms_data.reverse()
        snr_data = list(self.snr_buffer)
        snr_data.reverse()
        
        # Update frequency plot
        self.line_freq.set_data(time_ago, freq_data)
        if len(freq_data) > 0:
            ymax = max(20, max(freq_data) * 1.2)
            self.ax_freq.set_ylim(0, ymax)
        
        # Update amplitude plot
        self.line_amp.set_data(time_ago, amp_data)
        self.line_rms.set_data(time_ago, rms_data)
        if len(amp_data) > 0:
            ymax = max(100, max(amp_data) * 1.2)
            self.ax_amp.set_ylim(0, ymax)
        
        # Update SNR plot
        self.line_snr.set_data(time_ago, snr_data)
        if len(snr_data) > 0:
            ymax = max(40, max(snr_data) * 1.2)
            self.ax_snr.set_ylim(0, ymax)
    
    def run(self):
        """Run the clinical monitor"""
        print("\n" + "="*70)
        print("HFOV CLINICAL MONITOR")
        print("="*70)
        print("\nClinical Interface Features:")
        print("  • Real-time frequency and amplitude display")
        print("  • 60-second trend history")
        print("  • Automatic fault detection and alerts")
        print("  • System state monitoring")
        print("  • <2 second latency guarantee")
        print("\nControls:")
        print("  Q - Quit")
        print("="*70 + "\n")
        
        # Keyboard control
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        # Animation at 30 FPS for smooth, responsive waveform display
        self.anim = FuncAnimation(self.fig, self.update_plot, 
                                 interval=33, blit=False, cache_frame_data=False)
        
        plt.show()
        
        if self.serial_port:
            self.serial_port.close()
    
    def on_key(self, event):
        """Handle keyboard events"""
        if event.key == 'q':
            if self.serial_port:
                self.serial_port.close()
            plt.close(self.fig)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("HFOV CLINICAL MONITOR - Starting...")
    print("="*70)
    
    try:
        monitor = HFOVClinicalMonitor()
        monitor.run()
        
    except ConnectionError as e:
        print(f"\n{'='*70}")
        print(f"CONNECTION ERROR: {e}")
        print(f"{'='*70}")
        print("\nPlease check:")
        print("  1. Arduino is connected and powered")
        print("  2. Arduino code is uploaded")
        print("  3. Correct COM port")
        exit(1)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped by user")
        exit(0)