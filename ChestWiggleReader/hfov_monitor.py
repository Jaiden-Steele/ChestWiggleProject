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
        self.fs = 100  # 100 Hz sampling rate
        self.hfov_freq = 8.5  # Hz (typical HFOV frequency)
        self.current_time = 0
        self.is_paused = False
        self.data_window = 150  # samples (1.5 seconds at 100 Hz)
        
        # Serial connection
        self.serial_port = None
        self.use_synthetic = False
        
        # Data buffers using deque for efficient append/pop
        self.buffer_size = 500  # Keep extra data for filtering
        self.time_buffer = deque(maxlen=self.buffer_size)
        self.ax_buffer = deque(maxlen=self.buffer_size)
        self.ay_buffer = deque(maxlen=self.buffer_size)
        self.az_buffer = deque(maxlen=self.buffer_size)
        
        # Initialize serial connection
        if port:
            self.connect_serial(port, baudrate)
        else:
            self.auto_detect_arduino(baudrate)
        
        # Setup the plot
        self.setup_plot()
        
        # Stats
        self.frame_count = 0
        
    def auto_detect_arduino(self, baudrate):
        """Auto-detect Arduino on available serial ports"""
        print("\nSearching for Arduino...")
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            print("No serial ports found. Using synthetic data.")
            self.use_synthetic = True
            return
        
        print("\nAvailable ports:")
        for i, port in enumerate(ports):
            print(f"  {i+1}. {port.device} - {port.description}")
        
        # Try to find Arduino
        arduino_ports = [p for p in ports if 'Arduino' in p.description or 'CH340' in p.description or 'USB' in p.description]
        
        if arduino_ports:
            try:
                self.connect_serial(arduino_ports[0].device, baudrate)
                return
            except:
                pass
        
        # If auto-detect failed, ask user
        if len(ports) == 1:
            try:
                self.connect_serial(ports[0].device, baudrate)
                return
            except:
                pass
        
        print("\nCouldn't auto-detect Arduino. Using synthetic data.")
        print("To use real data, specify port manually: HFOVMonitor(port='COM3') or HFOVMonitor(port='/dev/ttyUSB0')")
        self.use_synthetic = True
    
    def connect_serial(self, port, baudrate):
        """Connect to Arduino via serial port"""
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=0.01)
            time.sleep(2)  # Wait for Arduino to reset
            self.serial_port.flushInput()  # Clear any old data
            print(f"\n✓ Connected to Arduino on {port} at {baudrate} baud")
            print("Waiting for data...\n")
            self.use_synthetic = False
        except Exception as e:
            print(f"\n✗ Failed to connect to {port}: {e}")
            print("Using synthetic data instead.\n")
            self.use_synthetic = True
            self.serial_port = None
    
    def read_serial_data(self):
        """Read one line of data from Arduino"""
        if not self.serial_port or not self.serial_port.is_open:
            return None
        
        try:
            if self.serial_port.in_waiting:
                line = self.serial_port.readline().decode('utf-8').strip()
                # Expected format: "ax,ay,az" or "timestamp,ax,ay,az"
                parts = line.split(',')
                
                if len(parts) == 3:
                    # Format: ax,ay,az
                    ax, ay, az = map(float, parts)
                    return ax, ay, az
                elif len(parts) == 4:
                    # Format: timestamp,ax,ay,az
                    _, ax, ay, az = map(float, parts)
                    return ax, ay, az
        except Exception as e:
            # Silently ignore parse errors (incomplete lines, etc.)
            pass
        
        return None
    
    def generate_synthetic_data(self, num_samples=1):
        """Generate synthetic HFOV data for testing"""
        t = (self.current_time + np.arange(num_samples)) / self.fs
        
        # HFOV signal
        hfov_signal = 0.04 * np.sin(2 * np.pi * self.hfov_freq * t)
        breathing_signal = 0.08 * np.sin(2 * np.pi * 0.3 * t)
        heartbeat_signal = 0.015 * np.sin(2 * np.pi * 1.2 * t)
        noise = (np.random.rand(num_samples) - 0.5) * 0.01
        
        ax = hfov_signal * 0.7 + breathing_signal * 0.5 + heartbeat_signal + noise
        ay = hfov_signal * 0.5 + breathing_signal * 0.3 + heartbeat_signal * 0.8 + noise
        az = hfov_signal * 0.9 + breathing_signal * 0.6 + heartbeat_signal * 0.5 + 1.0 + noise
        
        return ax[0], ay[0], az[0]
    
    def apply_bandpass_filter(self, data):
        """Apply Butterworth bandpass filter (5-15 Hz)"""
        if len(data) < 30:  # Need minimum data for filter
            return data
        
        sos = signal.butter(4, [5, 15], btype='band', fs=self.fs, output='sos')
        filtered = signal.sosfilt(sos, data)
        return filtered
    
    def setup_plot(self):
        """Setup the matplotlib figure and axes"""
        self.fig = plt.figure(figsize=(16, 11))
        title = 'HFOV Chest Oscillation Monitor - ' + ('LIVE DATA' if not self.use_synthetic else 'SYNTHETIC DATA')
        self.fig.suptitle(title, fontsize=16, fontweight='bold', y=0.98)
        
        # Create subplots with more spacing
        gs = self.fig.add_gridspec(4, 1, hspace=0.4, top=0.95, bottom=0.06, left=0.08, right=0.96)
        
        # Stats text area
        self.ax_stats = self.fig.add_subplot(gs[0, 0])
        self.ax_stats.axis('off')
        
        # Raw data plot
        self.ax_raw = self.fig.add_subplot(gs[1, 0])
        self.ax_raw.set_title('Before Filtering - Raw Accelerometer Data', fontweight='bold', pad=10)
        self.ax_raw.set_xlabel('Time (seconds)', fontsize=10)
        self.ax_raw.set_ylabel('Acceleration (g)', fontsize=10)
        self.ax_raw.grid(True, alpha=0.3)
        self.ax_raw.tick_params(axis='both', which='major', labelsize=9)
        
        # Filtered data plot
        self.ax_filt = self.fig.add_subplot(gs[2, 0])
        self.ax_filt.set_title('After Bandpass Filter (5-15 Hz) - Clean HFOV Signal', fontweight='bold', pad=10)
        self.ax_filt.set_xlabel('Time (seconds)', fontsize=10)
        self.ax_filt.set_ylabel('Acceleration (g)', fontsize=10)
        self.ax_filt.grid(True, alpha=0.3)
        self.ax_filt.tick_params(axis='both', which='major', labelsize=9)
        
        # Magnitude comparison plot
        self.ax_mag = self.fig.add_subplot(gs[3, 0])
        self.ax_mag.set_title('Vibration Magnitude Comparison', fontweight='bold', pad=10)
        self.ax_mag.set_xlabel('Time (seconds)', fontsize=10)
        self.ax_mag.set_ylabel('Vibration (millig)', fontsize=10)
        self.ax_mag.grid(True, alpha=0.3)
        self.ax_mag.tick_params(axis='both', which='major', labelsize=9)
        
        # Initialize lines
        self.lines_raw = {
            'x': self.ax_raw.plot([], [], 'r-', label='X-axis (raw)', linewidth=1.5)[0],
            'y': self.ax_raw.plot([], [], 'g-', label='Y-axis (raw)', linewidth=1.5)[0],
            'z': self.ax_raw.plot([], [], 'b-', label='Z-axis (raw)', linewidth=1.5)[0]
        }
        self.ax_raw.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        self.lines_filt = {
            'x': self.ax_filt.plot([], [], 'r-', label='X-axis (filtered)', linewidth=2)[0],
            'y': self.ax_filt.plot([], [], 'g-', label='Y-axis (filtered)', linewidth=2)[0],
            'z': self.ax_filt.plot([], [], 'b-', label='Z-axis (filtered)', linewidth=2)[0]
        }
        self.ax_filt.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        self.lines_mag = {
            'raw': self.ax_mag.plot([], [], color='gray', label='Raw (unfiltered)', 
                                   linewidth=2, alpha=0.6)[0],
            'filt': self.ax_mag.plot([], [], 'm-', label='Filtered (5-15 Hz)', 
                                    linewidth=2.5)[0]
        }
        self.ax_mag.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        # Stats text
        self.stats_text = self.ax_stats.text(0.5, 0.5, '', 
                                            ha='center', va='center',
                                            fontsize=11, family='monospace',
                                            bbox=dict(boxstyle='round', 
                                                     facecolor='lightblue' if not self.use_synthetic else 'lightyellow', 
                                                     alpha=0.8))
    
    def update_plot(self, frame):
        """Update function for animation"""
        if self.is_paused:
            return
        
        # Read new data (real or synthetic)
        if self.use_synthetic:
            ax, ay, az = self.generate_synthetic_data()
            # Add to buffers
            t = self.current_time / self.fs
            self.time_buffer.append(t)
            self.ax_buffer.append(ax)
            self.ay_buffer.append(ay)
            self.az_buffer.append(az)
            self.current_time += 1
        else:
            # Read multiple samples from serial buffer to catch up
            samples_read = 0
            max_samples = 20  # Read up to 20 samples per frame to prevent lag
            
            while samples_read < max_samples:
                data = self.read_serial_data()
                if data is None:
                    break  # No more data available
                
                ax, ay, az = data
                t = self.current_time / self.fs
                self.time_buffer.append(t)
                self.ax_buffer.append(ax)
                self.ay_buffer.append(ay)
                self.az_buffer.append(az)
                self.current_time += 1
                samples_read += 1
            
            # If no data was read, just return
            if samples_read == 0:
                return
        
        # Need minimum data to display
        if len(self.time_buffer) < 50:
            return
        
        # Get most recent window
        display_len = min(self.data_window, len(self.time_buffer))
        time_array = np.array(list(self.time_buffer))[-display_len:]
        ax_array = np.array(list(self.ax_buffer))[-display_len:]
        ay_array = np.array(list(self.ay_buffer))[-display_len:]
        az_array = np.array(list(self.az_buffer))[-display_len:]
        
        # Apply bandpass filter
        ax_filt = self.apply_bandpass_filter(np.array(list(self.ax_buffer)))[-display_len:]
        ay_filt = self.apply_bandpass_filter(np.array(list(self.ay_buffer)))[-display_len:]
        az_filt = self.apply_bandpass_filter(np.array(list(self.az_buffer)))[-display_len:]
        
        # Calculate magnitudes
        mag_raw = np.sqrt(ax_array**2 + ay_array**2 + az_array**2)
        mag_filt = np.sqrt(ax_filt**2 + ay_filt**2 + az_filt**2)
        
        # Update raw data lines
        self.lines_raw['x'].set_data(time_array, ax_array)
        self.lines_raw['y'].set_data(time_array, ay_array)
        self.lines_raw['z'].set_data(time_array, az_array)
        
        # Update filtered data lines
        self.lines_filt['x'].set_data(time_array, ax_filt)
        self.lines_filt['y'].set_data(time_array, ay_filt)
        self.lines_filt['z'].set_data(time_array, az_filt)
        
        # Update magnitude lines
        self.lines_mag['raw'].set_data(time_array, np.abs(mag_raw - 1.0) * 1000)
        self.lines_mag['filt'].set_data(time_array, mag_filt * 1000)
        
        # Set axis limits
        t_min, t_max = time_array[0], time_array[-1]
        
        self.ax_raw.set_xlim(t_min, t_max)
        self.ax_raw.set_ylim(-0.5, 1.5)
        
        self.ax_filt.set_xlim(t_min, t_max)
        self.ax_filt.set_ylim(-0.2, 0.2)
        
        self.ax_mag.set_xlim(t_min, t_max)
        self.ax_mag.set_ylim(0, 150)
        
        # Update stats (only every 5 frames)
        self.frame_count += 1
        if self.frame_count % 5 == 0:
            # Calculate actual stats from filtered data
            if len(ax_filt) > 10:
                peak_amp = np.max(mag_filt) * 1000  # millig
                rms_vib = np.sqrt(np.mean(mag_filt**2)) * 1000  # millig
            else:
                peak_amp = 0
                rms_vib = 0
            
            mode = "LIVE" if not self.use_synthetic else "SYNTHETIC"
            stats_str = f"""
┌──────────────────────────────────────────────────────────────────────────┐
│  Mode: {mode:10s}  │  Peak Amplitude: {peak_amp:.1f} mg  │  RMS Vibration: {rms_vib:.1f} mg  │
│  Status: {'PAUSED' if self.is_paused else 'RUNNING'}  │  Buffer: {len(self.time_buffer)}/{self.buffer_size}  │  Time: {t:.1f}s  │
└──────────────────────────────────────────────────────────────────────────┘
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
        if self.serial_port:
            self.serial_port.flushInput()
        print("Monitor RESET")
    
    def run(self):
        """Run the monitor"""
        # Add keyboard controls
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        # Create animation
        self.anim = FuncAnimation(self.fig, self.update_plot, 
                                 interval=50,  # 50ms = 20 FPS for smooth display
                                 blit=False, cache_frame_data=False)
        
        # Show instructions
        print("\n" + "="*70)
        print("HFOV CHEST OSCILLATION MONITOR")
        print("="*70)
        print("Controls:")
        print("  SPACE - Pause/Resume")
        print("  R     - Reset")
        print("  Q     - Quit")
        print("\nArduino Data Format:")
        print("  Expected: 'ax,ay,az' or 'timestamp,ax,ay,az'")
        print("  Units: Acceleration in g's (e.g., 0.05, 1.02, -0.15)")
        print("  Example: '0.05,0.02,1.01' or '1234,0.05,0.02,1.01'")
        print("="*70 + "\n")
        
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
    # Auto-detect Arduino
    monitor = HFOVMonitor()
    
    # Or manually specify port:
    # Windows: monitor = HFOVMonitor(port='COM3')
    # Linux/Mac: monitor = HFOVMonitor(port='/dev/ttyUSB0')
    # Custom baudrate: monitor = HFOVMonitor(port='COM3', baudrate=9600)
    
    monitor.run()