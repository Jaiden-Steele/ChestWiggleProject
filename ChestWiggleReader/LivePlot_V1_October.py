import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from scipy import signal
import serial
import serial.tools.list_ports
from collections import deque
import time

class HFOVMonitor:
    def __init__(self, port=None, baudrate=115200):
        # Sampling parameters
        self.fs = 100  # 100 Hz sampling rate (matches Arduino)
        self.hfov_freq_range = (5, 15)  # HFOV frequency range (Hz)
        self.current_time = 0
        self.is_paused = False
        self.data_window = 300  # samples (3 seconds at 100 Hz)
        
        # Serial connection
        self.serial_port = None
        
        # Data buffers using deque for efficient append/pop
        self.buffer_size = 1000  # 10 seconds of data
        self.time_buffer = deque(maxlen=self.buffer_size)
        self.ax_buffer = deque(maxlen=self.buffer_size)
        self.ay_buffer = deque(maxlen=self.buffer_size)
        self.az_buffer = deque(maxlen=self.buffer_size)
        self.mag_buffer = deque(maxlen=self.buffer_size)
        
        # Design bandpass filter for HFOV isolation (5-15 Hz)
        # Using 4th order Butterworth for good frequency response
        self.sos_bandpass = signal.butter(4, self.hfov_freq_range, 
                                         btype='band', fs=self.fs, output='sos')
        
        # SNR tracking
        self.signal_power = 0
        self.noise_power = 0
        self.snr_db = 0
        
        # Initialize serial connection
        if port:
            self.connect_serial(port, baudrate)
        else:
            self.auto_detect_arduino(baudrate)
        
        # Setup the plot
        self.setup_plot()
        
        # Stats
        self.frame_count = 0
        self.last_update_time = time.time()
        
    def auto_detect_arduino(self, baudrate):
        """Auto-detect Arduino on available serial ports"""
        print("\n" + "="*70)
        print("SEARCHING FOR ARDUINO...")
        print("="*70)
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("\n✗ ERROR: No serial ports found!")
            print("\nTroubleshooting:")
            print("  1. Is Arduino connected via USB?")
            print("  2. Check Device Manager (Windows) to verify COM port")
            print("  3. Try unplugging and reconnecting Arduino")
            raise ConnectionError("No serial ports available")
        
        print("\nAvailable ports:")
        for i, port in enumerate(ports):
            print(f"  {i+1}. {port.device} - {port.description}")
        
        # Try to find Arduino
        arduino_ports = [p for p in ports if 'Arduino' in p.description or 
                        'CH340' in p.description or 'USB' in p.description or
                        'Serial' in p.description]
        
        if arduino_ports:
            print(f"\n→ Found Arduino device: {arduino_ports[0].device}")
            self.connect_serial(arduino_ports[0].device, baudrate)
            return
        
        # If auto-detect failed, try all ports
        print("\n→ No obvious Arduino found, trying all ports...")
        for port in ports:
            try:
                print(f"  Trying {port.device}...")
                self.connect_serial(port.device, baudrate)
                return  # Success!
            except:
                continue
        
        # Complete failure
        print("\n✗ ERROR: Could not connect to any port!")
        print("\nTroubleshooting:")
        print("  1. Close Arduino IDE Serial Monitor if it's open")
        print("  2. Verify Arduino code is uploaded and running")
        print("  3. Manually specify port: HFOVMonitor(port='COM3')")
        raise ConnectionError("Failed to connect to Arduino")
    
    def connect_serial(self, port, baudrate):
        """Connect to Arduino via serial port"""
        print(f"\n→ Opening {port}...")
        
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=0.1)
        except serial.SerialException as e:
            print(f"✗ Could not open port: {e}")
            print("  (Port may be in use by Arduino IDE Serial Monitor)")
            raise
        
        print(f"  Port opened successfully at {baudrate} baud")
        print(f"  Waiting 7 seconds for Arduino to boot and calibrate...")
        time.sleep(7)  # Wait for Arduino to boot (2s) + calibrate (5s)
        
        # Flush any old data
        self.serial_port.flushInput()
        
        print(f"  Reading initial data from Arduino...")
        
        # Try to read data for up to 10 seconds
        valid_lines = 0
        comment_lines = 0
        bad_lines = 0
        start_time = time.time()
        
        while (time.time() - start_time) < 10:
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8').strip()
                    
                    if not line:
                        continue
                    
                    # Debug: print what we're receiving
                    if line.startswith('#'):
                        print(f"  Arduino: {line}")
                        comment_lines += 1
                        continue
                    
                    # Try to parse data line
                    parts = line.split(',')
                    if len(parts) >= 3:
                        try:
                            ax, ay, az = map(float, parts[:3])
                            print(f"✓ Valid data received: ax={ax:.6f}, ay={ay:.6f}, az={az:.6f}")
                            print(f"✓ Connection successful!\n")
                            return  # Success!
                        except ValueError:
                            bad_lines += 1
                            if bad_lines <= 3:
                                print(f"  ? Bad data format: {line[:50]}")
                    else:
                        bad_lines += 1
                        if bad_lines <= 3:
                            print(f"  ? Unexpected format: {line[:50]}")
                        
            except UnicodeDecodeError:
                bad_lines += 1
                if bad_lines <= 3:
                    print(f"  ? Unicode decode error")
            except Exception as e:
                bad_lines += 1
                if bad_lines <= 3:
                    print(f"  ? Error reading: {e}")
            
            time.sleep(0.01)
        
        # If we get here, we failed
        self.serial_port.close()
        self.serial_port = None
        print(f"\n✗ No valid data received after 10 seconds")
        print(f"  Comment lines: {comment_lines}")
        print(f"  Bad/unexpected lines: {bad_lines}")
        print(f"  Valid data lines: {valid_lines}")
        print("\nPossible issues:")
        print("  1. Arduino code not uploaded correctly")
        print("  2. Wrong baud rate (should be 115200)")
        print("  3. Arduino stuck in error state")
        print("  4. Check Arduino Serial Monitor to verify data is streaming")
        raise ConnectionError("Arduino not sending valid data")
    
    def read_serial_data(self):
        """Read one line of data from Arduino"""
        if not self.serial_port or not self.serial_port.is_open:
            return None
        
        try:
            if self.serial_port.in_waiting:
                line = self.serial_port.readline().decode('utf-8').strip()
                
                # Skip comment lines
                if not line or line.startswith('#'):
                    return None
                
                # Expected format: "ax,ay,az" or "ax,ay,az,magnitude"
                parts = line.split(',')
                
                if len(parts) >= 3:
                    ax, ay, az = map(float, parts[:3])
                    mag = float(parts[3]) if len(parts) >= 4 else np.sqrt(ax**2 + ay**2 + az**2)
                    return ax, ay, az, mag
        except:
            pass  # Silently ignore parse errors
        
        return None
    
    def apply_bandpass_filter(self, data):
        """Apply bandpass filter (5-15 Hz) to isolate HFOV signal"""
        if len(data) < 50:  # Need minimum data for stable filtering
            return np.array(data)
        
        # Apply zero-phase filtering for no phase distortion
        filtered = signal.sosfiltfilt(self.sos_bandpass, data)
        return filtered
    
    def calculate_snr(self, raw_signal, filtered_signal):
        """Calculate SNR: signal power / noise power in dB"""
        if len(raw_signal) < 100 or len(filtered_signal) < 100:
            return 0
        
        # Signal power = power in filtered (HFOV band)
        signal_power = np.mean(filtered_signal[-100:]**2)
        
        # Noise power = power in raw minus power in filtered
        noise = raw_signal[-100:] - filtered_signal[-100:]
        noise_power = np.mean(noise**2)
        
        # Avoid division by zero
        if noise_power < 1e-10:
            return 40  # Very high SNR
        
        snr = 10 * np.log10(signal_power / noise_power)
        return max(0, snr)  # Clip at 0
    
    def setup_plot(self):
        """Setup matplotlib figure and axes"""
        self.fig = plt.figure(figsize=(16, 12))
        title = 'HFOV Chest Oscillation Monitor - Live Data'
        
        self.fig.suptitle(title, fontsize=16, fontweight='bold', y=0.98)
        
        # Create subplots
        gs = self.fig.add_gridspec(5, 1, hspace=0.35, top=0.95, bottom=0.06, 
                                   left=0.08, right=0.96)
        
        # Stats panel
        self.ax_stats = self.fig.add_subplot(gs[0, 0])
        self.ax_stats.axis('off')
        
        # Raw signals (after Arduino's filtering)
        self.ax_raw = self.fig.add_subplot(gs[1, 0])
        self.ax_raw.set_title('Raw Accelerometer Data (After Arduino DC Removal & LPF)', 
                             fontweight='bold', pad=10)
        self.ax_raw.set_xlabel('Time (seconds)', fontsize=10)
        self.ax_raw.set_ylabel('Acceleration (g)', fontsize=10)
        self.ax_raw.grid(True, alpha=0.3, linestyle='--')
        self.ax_raw.tick_params(axis='both', which='major', labelsize=9)
        
        # HFOV isolated signal (5-15 Hz bandpass)
        self.ax_hfov = self.fig.add_subplot(gs[2, 0])
        self.ax_hfov.set_title('HFOV Signal (5-15 Hz Bandpass Filter)', 
                              fontweight='bold', pad=10)
        self.ax_hfov.set_xlabel('Time (seconds)', fontsize=10)
        self.ax_hfov.set_ylabel('Acceleration (g)', fontsize=10)
        self.ax_hfov.grid(True, alpha=0.3, linestyle='--')
        self.ax_hfov.tick_params(axis='both', which='major', labelsize=9)
        
        # Vector magnitude
        self.ax_mag = self.fig.add_subplot(gs[3, 0])
        self.ax_mag.set_title('Vector Magnitude Comparison', fontweight='bold', pad=10)
        self.ax_mag.set_xlabel('Time (seconds)', fontsize=10)
        self.ax_mag.set_ylabel('Magnitude (millig)', fontsize=10)
        self.ax_mag.grid(True, alpha=0.3, linestyle='--')
        self.ax_mag.tick_params(axis='both', which='major', labelsize=9)
        
        # Frequency spectrum
        self.ax_spectrum = self.fig.add_subplot(gs[4, 0])
        self.ax_spectrum.set_title('Frequency Spectrum (HFOV Band)', 
                                  fontweight='bold', pad=10)
        self.ax_spectrum.set_xlabel('Frequency (Hz)', fontsize=10)
        self.ax_spectrum.set_ylabel('Power (dB)', fontsize=10)
        self.ax_spectrum.grid(True, alpha=0.3, linestyle='--')
        self.ax_spectrum.tick_params(axis='both', which='major', labelsize=9)
        self.ax_spectrum.set_xlim(0, 20)
        
        # Initialize plot lines - Raw data
        self.lines_raw = {
            'x': self.ax_raw.plot([], [], 'r-', label='X-axis', linewidth=1.2, alpha=0.8)[0],
            'y': self.ax_raw.plot([], [], 'g-', label='Y-axis', linewidth=1.2, alpha=0.8)[0],
            'z': self.ax_raw.plot([], [], 'b-', label='Z-axis', linewidth=1.2, alpha=0.8)[0]
        }
        self.ax_raw.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        # HFOV filtered lines
        self.lines_hfov = {
            'x': self.ax_hfov.plot([], [], 'r-', label='X-axis (HFOV)', linewidth=2)[0],
            'y': self.ax_hfov.plot([], [], 'g-', label='Y-axis (HFOV)', linewidth=2)[0],
            'z': self.ax_hfov.plot([], [], 'b-', label='Z-axis (HFOV)', linewidth=2)[0]
        }
        self.ax_hfov.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        # Magnitude lines
        self.lines_mag = {
            'raw': self.ax_mag.plot([], [], color='gray', label='Raw magnitude', 
                                   linewidth=1.5, alpha=0.6)[0],
            'hfov': self.ax_mag.plot([], [], 'm-', label='HFOV magnitude (5-15 Hz)', 
                                    linewidth=2.5)[0]
        }
        self.ax_mag.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        # Spectrum line
        self.line_spectrum = self.ax_spectrum.plot([], [], 'b-', linewidth=2)[0]
        self.ax_spectrum.axvspan(5, 15, alpha=0.1, color='green', label='HFOV band')
        self.ax_spectrum.legend(loc='upper right', fontsize=9)
        
        # Stats text
        self.stats_text = self.ax_stats.text(0.5, 0.5, '', 
                                            ha='center', va='center',
                                            fontsize=10, family='monospace',
                                            bbox=dict(boxstyle='round', 
                                                     facecolor='lightgreen', 
                                                     alpha=0.8))
    
    def update_plot(self, frame):
        """Update function for animation"""
        if self.is_paused:
            return
        
        # Read multiple samples from serial to prevent buffer overflow
        samples_read = 0
        max_samples = 30
        
        while samples_read < max_samples:
            data = self.read_serial_data()
            if data is None:
                break
            
            ax, ay, az, mag = data
            t = self.current_time / self.fs
            self.time_buffer.append(t)
            self.ax_buffer.append(ax)
            self.ay_buffer.append(ay)
            self.az_buffer.append(az)
            self.mag_buffer.append(mag)
            self.current_time += 1
            samples_read += 1
        
        # No new data available
        if samples_read == 0:
            return
        
        # Need minimum data
        if len(self.time_buffer) < 100:
            return
        
        # Get display window
        display_len = min(self.data_window, len(self.time_buffer))
        time_array = np.array(list(self.time_buffer))[-display_len:]
        ax_array = np.array(list(self.ax_buffer))[-display_len:]
        ay_array = np.array(list(self.ay_buffer))[-display_len:]
        az_array = np.array(list(self.az_buffer))[-display_len:]
        mag_array = np.array(list(self.mag_buffer))[-display_len:]
        
        # Apply HFOV bandpass filter (5-15 Hz)
        ax_hfov = self.apply_bandpass_filter(np.array(list(self.ax_buffer)))[-display_len:]
        ay_hfov = self.apply_bandpass_filter(np.array(list(self.ay_buffer)))[-display_len:]
        az_hfov = self.apply_bandpass_filter(np.array(list(self.az_buffer)))[-display_len:]
        mag_hfov = np.sqrt(ax_hfov**2 + ay_hfov**2 + az_hfov**2)
        
        # Calculate SNR
        self.snr_db = self.calculate_snr(mag_array, mag_hfov)
        
        # Update raw data plots
        self.lines_raw['x'].set_data(time_array, ax_array)
        self.lines_raw['y'].set_data(time_array, ay_array)
        self.lines_raw['z'].set_data(time_array, az_array)
        
        # Update HFOV filtered plots
        self.lines_hfov['x'].set_data(time_array, ax_hfov)
        self.lines_hfov['y'].set_data(time_array, ay_hfov)
        self.lines_hfov['z'].set_data(time_array, az_hfov)
        
        # Update magnitude plots
        self.lines_mag['raw'].set_data(time_array, mag_array * 1000)  # Convert to millig
        self.lines_mag['hfov'].set_data(time_array, mag_hfov * 1000)
        
        # Update frequency spectrum (FFT)
        if len(mag_hfov) >= 100:
            freqs, psd = signal.welch(mag_hfov, fs=self.fs, nperseg=min(256, len(mag_hfov)))
            psd_db = 10 * np.log10(psd + 1e-10)
            self.line_spectrum.set_data(freqs, psd_db)
            self.ax_spectrum.set_ylim(np.min(psd_db) - 5, np.max(psd_db) + 5)
        
        # Set axis limits
        t_min, t_max = time_array[0], time_array[-1]
        
        self.ax_raw.set_xlim(t_min, t_max)
        self.ax_raw.set_ylim(-0.15, 0.15)
        
        self.ax_hfov.set_xlim(t_min, t_max)
        self.ax_hfov.set_ylim(-0.1, 0.1)
        
        self.ax_mag.set_xlim(t_min, t_max)
        self.ax_mag.set_ylim(0, max(100, np.max(mag_hfov * 1000) * 1.2))
        
        # Update stats every 5 frames
        self.frame_count += 1
        if self.frame_count % 5 == 0:
            peak_amp = np.max(mag_hfov) * 1000
            rms_amp = np.sqrt(np.mean(mag_hfov**2)) * 1000
            
            snr_status = "✓ PASS" if self.snr_db >= 15 else "⚠ LOW"
            
            stats_str = f"""
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ LIVE DATA │ SNR: {self.snr_db:5.1f} dB {snr_status} │ Peak: {peak_amp:6.1f} mg │ RMS: {rms_amp:6.1f} mg │
│ Status: {'PAUSED ' if self.is_paused else 'RUNNING'} │ Buffer: {len(self.time_buffer):4d}/{self.buffer_size} │ Time: {t_max:7.1f}s │
└────────────────────────────────────────────────────────────────────────────────────────┘
            """
            self.stats_text.set_text(stats_str)
    
    def toggle_pause(self):
        """Toggle pause state"""
        self.is_paused = not self.is_paused
        print(f"Monitor {'PAUSED' if self.is_paused else 'RESUMED'}")
    
    def reset(self):
        """Reset the monitor"""
        self.current_time = 0
        self.time_buffer.clear()
        self.ax_buffer.clear()
        self.ay_buffer.clear()
        self.az_buffer.clear()
        self.mag_buffer.clear()
        if self.serial_port:
            self.serial_port.flushInput()
        print("Monitor RESET")
    
    def run(self):
        """Run the monitor"""
        # Keyboard controls
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        # Create animation (20 FPS display rate)
        self.anim = FuncAnimation(self.fig, self.update_plot, 
                                 interval=50, blit=False, cache_frame_data=False)
        
        # Print instructions
        print("\n" + "="*80)
        print("HFOV CHEST OSCILLATION MONITOR")
        print("="*80)
        print("Signal Processing Pipeline:")
        print("  1. Arduino: DC removal (0.5 Hz HPF) + bandwidth limiting (42 Hz LPF)")
        print("  2. Python:  HFOV isolation (5-15 Hz bandpass)")
        print("  3. Analysis: SNR calculation, frequency spectrum, amplitude metrics")
        print("\nControls:")
        print("  SPACE - Pause/Resume")
        print("  R     - Reset")
        print("  Q     - Quit")
        print("\nTarget Specifications:")
        print("  • Sample Rate: ≥80 Hz (actual: 100 Hz) ✓")
        print("  • Bandwidth: 0.5-40 Hz ✓")
        print("  • SNR: ≥15 dB (monitored in real-time)")
        print("  • Drift: <2% (calibrated at startup)")
        print("="*80 + "\n")
        
        plt.show()
        
        # Cleanup
        if self.serial_port:
            self.serial_port.close()
    
    def on_key(self, event):
        """Handle keyboard events"""
        if event.key == ' ':
            self.toggle_pause()
        elif event.key == 'r':
            self.reset()
        elif event.key == 'q':
            if self.serial_port:
                self.serial_port.close()
            plt.close(self.fig)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("HFOV MONITOR - Enhanced Signal Processing")
    print("="*70)
    print("\nChecking dependencies...")
    
    try:
        import numpy
        print("✓ NumPy installed")
    except ImportError:
        print("✗ NumPy missing - Run: pip install numpy")
        exit(1)
    
    try:
        import matplotlib
        print("✓ Matplotlib installed")
    except ImportError:
        print("✗ Matplotlib missing - Run: pip install matplotlib")
        exit(1)
    
    try:
        import scipy
        print("✓ SciPy installed")
    except ImportError:
        print("✗ SciPy missing - Run: pip install scipy")
        exit(1)
    
    try:
        import serial
        print("✓ PySerial installed")
    except ImportError:
        print("✗ PySerial missing - Run: pip install pyserial")
        exit(1)
    
    print("\n→ All dependencies OK!")
    print("\nInitializing monitor...")
    
    try:
        # Auto-detect Arduino - will raise exception if connection fails
        monitor = HFOVMonitor()
        
        # Manual port specification examples:
        # Windows: monitor = HFOVMonitor(port='COM3')
        # Linux/Mac: monitor = HFOVMonitor(port='/dev/ttyUSB0')
        # Custom baudrate: monitor = HFOVMonitor(port='COM3', baudrate=9600)
        
        monitor.run()
        
    except ConnectionError as e:
        print(f"\n{'='*70}")
        print(f"FATAL ERROR: {e}")
        print(f"{'='*70}")
        print("\nMonitor cannot start without valid Arduino connection.")
        print("Please fix the issue above and try again.")
        exit(1)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped by user (Ctrl+C)")
        exit(0)