📋 Overview
The HFOV Chest Oscillation Monitor is a senior design project addressing an unmet clinical need in pediatric and neonatal intensive care units (PICU/NICU). Currently, respiratory therapists assess the "chest wiggle factor" (CWF) visually, making it highly subjective and prone to error. Our solution provides objective, quantitative measurements of chest oscillations during HFOV therapy.
The Problem

Current Method: Visual assessment of chest oscillations by respiratory therapists
Limitations: Subjective, inconsistent between observers, difficult to document
Impact: Uncertainty in ventilation effectiveness, risk of improper treatment

Our Solution
A wearable accelerometer-based device that:

✅ Provides real-time, quantitative measurements of chest oscillations
✅ Non-invasive and safe for use with infants
✅ Displays filtered HFOV signals (5-15 Hz) with noise reduction
✅ Visualizes vibration magnitude and frequency in real-time

🎯 Key Features

Real-time Monitoring: Live visualization of chest oscillations at 100 Hz sampling rate
Advanced Signal Processing: Butterworth bandpass filter (5-15 Hz) isolates HFOV signals
Multi-axis Tracking: Independent X, Y, Z acceleration monitoring with LED indicators
Flexible Data Input: Supports both live Arduino data and synthetic testing data
Clinical Insights: Displays peak amplitude, RMS vibration, and frequency analysis
User-Friendly Interface: Pause/resume, reset controls, and clear visual feedback

🏥 Clinical Context
Intended Use: Monitoring chest wall oscillations in PICU/NICU patients (≤5 years old) undergoing HFOV
User: Respiratory therapists in pediatric intensive care settings
HFOV Parameters: Typical oscillation frequency of 5-15 Hz (device optimized for 8.5 Hz)
🛠️ System Architecture
┌─────────────────┐      USB Serial       ┌──────────────────┐
│  MPU6050 IMU    │ ───────────────────► │   Python GUI     │
│  (Arduino)      │    100 Hz @ 115200   │  (Matplotlib)    │
│                 │       baud            │                  │
│ • 3-axis accel  │                       │ • Real-time plot │
│ • ±2g range     │                       │ • Bandpass filter│
│ • 20Hz DLPF     │                       │ • Stats display  │
│ • Calibration   │                       │ • Visual alerts  │
└─────────────────┘                       └──────────────────┘
📦 Hardware Requirements

Microcontroller: Arduino Uno/Nano or compatible
Sensor: MPU6050 6-axis IMU (accelerometer + gyroscope)
Indicators: 3x LEDs (Red, Green, Blue) for axis-specific alerts
Connections:

MPU6050 → Arduino I2C (SDA, SCL)
LEDs → Digital pins 8, 9, 10 (with appropriate resistors)
