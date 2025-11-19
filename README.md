# HFOV Chest Oscillation Monitor

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Arduino](https://img.shields.io/badge/Arduino-Compatible-00979D.svg)](https://www.arduino.cc/)

> A real-time monitoring system for quantifying chest wall oscillations in pediatric patients undergoing High-Frequency Oscillatory Ventilation (HFOV)

## 📋 Overview

The HFOV Chest Oscillation Monitor is a senior design project addressing an unmet clinical need in pediatric and neonatal intensive care units (PICU/NICU). Currently, respiratory therapists assess the "chest wiggle factor" (CWF) visually, making it highly subjective and prone to error. Our solution provides objective, quantitative measurements of chest oscillations during HFOV therapy.

### The Problem

- **Current Method**: Visual assessment of chest oscillations by respiratory therapists
- **Limitations**: Subjective, inconsistent between observers, difficult to document
- **Impact**: Uncertainty in ventilation effectiveness, risk of improper treatment

### Our Solution

A wearable accelerometer-based device that:
- ✅ Provides real-time, quantitative measurements of chest oscillations
- ✅ Non-invasive and safe for use with infants
- ✅ Displays filtered HFOV signals (5-15 Hz) with noise reduction
- ✅ Visualizes vibration magnitude and frequency in real-time

## 🎯 Key Features

- **Real-time Monitoring**: Live visualization of chest oscillations at 100 Hz sampling rate
- **Advanced Signal Processing**: Butterworth bandpass filter (5-15 Hz) isolates HFOV signals
- **Multi-axis Tracking**: Independent X, Y, Z acceleration monitoring with LED indicators
- **Flexible Data Input**: Supports both live Arduino data and synthetic testing data
- **Clinical Insights**: Displays peak amplitude, RMS vibration, and frequency analysis
- **User-Friendly Interface**: Pause/resume, reset controls, and clear visual feedback

## 🏥 Clinical Context

**Intended Use**: Monitoring chest wall oscillations in PICU/NICU patients (≤5 years old) undergoing HFOV

**User**: Respiratory therapists in pediatric intensive care settings

**HFOV Parameters**: Typical oscillation frequency of 5-15 Hz (device optimized for 8.5 Hz)

## 🛠️ System Architecture

```
┌─────────────────┐      USB Serial       ┌──────────────────┐
│  MPU6050 IMU    │ ───────────────────► │   Python GUI     │
│  (Arduino)      │    100 Hz @ 115200   │  (Matplotlib)    │
│                 │       baud            │                  │
│ • 3-axis accel  │                       │ • Real-time plot │
│ • ±2g range     │                       │ • Bandpass filter│
│ • 20Hz DLPF     │                       │ • Stats display  │
│ • Calibration   │                       │ • Visual alerts  │
└─────────────────┘                       └──────────────────┘
```

## 📦 Hardware Requirements

- **Microcontroller**: Arduino Uno/Nano or compatible
- **Sensor**: MPU6050 6-axis IMU (accelerometer + gyroscope)
- **Indicators**: 3x LEDs (Red, Green, Blue) for axis-specific alerts
- **Connections**:
  - MPU6050 → Arduino I2C (SDA, SCL)
  - LEDs → Digital pins 8, 9, 10 (with appropriate resistors)

### Wiring Diagram

```
MPU6050          Arduino
────────         ───────
VCC    ──────►   5V
GND    ──────►   GND
SDA    ──────►   A4 (SDA)
SCL    ──────►   A5 (SCL)

LEDs             Arduino
────             ───────
Red LED   ──────► Pin 8  (X-axis deviation)
Green LED ──────► Pin 9  (Y-axis deviation)
Blue LED  ──────► Pin 10 (Z-axis deviation)
```

## 💻 Software Requirements

### Python Dependencies
```bash
numpy>=1.21.0
matplotlib>=3.5.0
scipy>=1.7.0
pyserial>=3.5
```

### Arduino Libraries
- Wire (built-in)
- MPU6050 by Electronic Cats

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/hfov-monitor.git
cd hfov-monitor
```

### 2. Install Python Dependencies
```bash
pip install numpy matplotlib scipy pyserial
```

### 3. Install Arduino Libraries
1. Open Arduino IDE
2. Go to **Sketch → Include Library → Manage Libraries**
3. Search for "MPU6050" by Electronic Cats
4. Click **Install**

### 4. Upload Arduino Firmware
1. Connect your Arduino via USB
2. Open `arduino/hfov_sensor.ino` in Arduino IDE
3. Select your board and port from **Tools** menu
4. Click **Upload** (→)

## 📊 Usage

### Quick Start

1. **Hardware Setup**:
   - Ensure MPU6050 is securely connected to Arduino
   - Upload the appropriate Arduino sketch
   - Place sensor on test surface or patient (when approved for clinical use)

2. **Run Monitor**:
   ```bash
   python hfov_monitor.py
   ```

3. **Auto-Detection**:
   - The software will automatically detect your Arduino
   - If detection fails, it will run with synthetic data for testing

4. **Manual Port Selection** (if needed):
   ```python
   # Windows
   monitor = HFOVMonitor(port='COM3')
   
   # Linux/Mac
   monitor = HFOVMonitor(port='/dev/ttyUSB0')
   ```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `SPACE` | Pause/Resume monitoring |
| `R` | Reset buffers and restart |
| `Q` | Quit application |

### Data Format

**Arduino Output** (CSV format):
```
ax,ay,az                    # 3 values
timestamp,ax,ay,az          # 4 values (optional timestamp)
```

Where `ax`, `ay`, `az` are acceleration values in *g* units (e.g., `0.05`, `1.02`, `-0.15`)

## 📈 Understanding the Display

The monitor shows three synchronized plots:

### 1. Raw Accelerometer Data
- Shows unfiltered X, Y, Z acceleration
- Includes breathing, heartbeat, and HFOV oscillations
- Noise and baseline drift visible

### 2. Filtered HFOV Signal (5-15 Hz)
- Bandpass filtered to isolate HFOV frequencies
- Clear oscillation patterns
- Removes breathing (~0.3 Hz) and baseline drift

### 3. Vibration Magnitude Comparison
- **Gray line**: Raw unfiltered magnitude
- **Magenta line**: Filtered HFOV magnitude (5-15 Hz)
- Units: millig (1 mg = 0.001 g)

### Status Panel
```
┌────────────────────────────────────────────────────────────────────┐
│  Mode: LIVE        │  Peak Amplitude: 45.2 mg  │  RMS Vibration: 32.1 mg  │
│  Status: RUNNING   │  Buffer: 150/500          │  Time: 12.5s             │
└────────────────────────────────────────────────────────────────────┘
```

## 🔧 Arduino Firmware Options

### Version 1: LED Indicator Firmware
**File**: `arduino/led_indicator.ino`

**Features**:
- Real-time LED feedback for each axis
- Calibration routine on startup
- Threshold-based alerts (0.20g default)
- Serial debug output

**LED Behavior**:
- 🔴 **Red LED**: X-axis deviation (forward/back)
- 🟢 **Green LED**: Y-axis deviation (side-to-side)
- 🔵 **Blue LED**: Z-axis deviation (up/down)

### Version 2: Data Streaming Firmware
**File**: `arduino/data_streaming.ino`

**Features**:
- Optimized for Python GUI integration
- 100 Hz sampling rate
- Digital low-pass filter (20 Hz)
- Calibrated output in g units
- Magnitude and vibration calculations

**Use Case**: Primary firmware for the monitoring GUI

## 🔬 Technical Specifications

| Parameter | Value |
|-----------|-------|
| Sampling Rate | 100 Hz |
| HFOV Frequency Range | 5-15 Hz |
| Accelerometer Range | ±2g |
| Digital Filter | Butterworth 4th order bandpass |
| Data Buffer | 500 samples (5 seconds) |
| Display Window | 150 samples (1.5 seconds) |
| Update Rate | 20 FPS |

## 🎓 User Needs Addressed

Based on ethnographic observations and interviews with respiratory therapists:

1. ✅ **Accuracy across patient variability**: Calibration system adapts to different body sizes
2. ✅ **Secure application**: Lightweight, medical-grade adhesive mounting
3. ✅ **Sterilization compatibility**: Device design considers clinical hygiene protocols
4. ✅ **System integration**: Serial output compatible with existing monitoring systems
5. ✅ **Compact design**: Small form factor, non-obstructive
6. ✅ **Rapid deployment**: Quick calibration and setup (<2 minutes)
7. ✅ **Motion tolerance**: Advanced filtering maintains signal quality during patient movement
8. ✅ **Continuous monitoring**: Buffer system prevents data loss
9. ✅ **Long battery life**: Low-power sensor with efficient sampling

## 🧪 Testing

### Synthetic Data Mode
Test the GUI without hardware:
```python
from hfov_monitor import HFOVMonitor

monitor = HFOVMonitor()  # Auto-falls back to synthetic if no Arduino found
monitor.run()
```

The synthetic signal includes:
- HFOV oscillations (8.5 Hz)
- Breathing (0.3 Hz)
- Heartbeat (1.2 Hz)
- Random noise

### Calibration Testing
1. Place sensor on flat, stable surface
2. Run Arduino firmware
3. Keep sensor motionless during calibration prompt
4. Verify LEDs respond to gentle tilting

## 📝 Future Development

- [ ] Wireless data transmission (Bluetooth/WiFi)
- [ ] Integration with hospital EHR systems
- [ ] Machine learning for anomaly detection
- [ ] Multi-patient monitoring dashboard
- [ ] FDA regulatory submission preparation
- [ ] Clinical trial data collection

## ⚠️ Disclaimer

**This device is a prototype for educational and research purposes only.**

- Not FDA approved for clinical use
- Not intended for diagnostic or therapeutic decisions
- Requires clinical validation and regulatory approval before patient use
- Always follow hospital protocols and physician guidance

## 👥 Team

**Senior Design Project** - University of Pittsburgh
- Connor Rees - Project Lead
- Isabella Hsia - Financial Lead
- Jaiden Steele
- Isa Lisi

**Clinical Consultant**: Former Respiratory Therapist with 35+ years experience

## 🙏 Acknowledgments

- Respiratory therapists at UPMC for clinical insights
- University of Pittsburgh Department of Biomedical Engineering
- Electronic Cats for MPU6050 Arduino library
- Open-source Python community

## 📧 Contact

For questions, collaboration, or clinical feedback:
- **Email**: cwr31@pitt.edu

---

<div align="center">

**Made with ❤️ for improving pediatric critical care**

[Report Bug](https://github.com/yourusername/hfov-monitor/issues) · [Request Feature](https://github.com/yourusername/hfov-monitor/issues) · [Documentation](https://github.com/yourusername/hfov-monitor/wiki)

</div>
