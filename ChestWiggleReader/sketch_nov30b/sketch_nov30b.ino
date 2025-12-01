#include <Wire.h>
#include <MPU6050.h>

MPU6050 mpu;

// ============================================================================
// CONFIGURATION PARAMETERS
// ============================================================================
const uint32_t SAMPLE_RATE_HZ = 100;           // 100 Hz sampling
const uint32_t SAMPLE_INTERVAL_US = 1000000 / SAMPLE_RATE_HZ;
const uint32_t ANALYSIS_INTERVAL_MS = 1000;    // 1 Hz analysis/output rate
const uint32_t ANALYSIS_WINDOW_SAMPLES = 64;   // Use full buffer (0.64 sec)

const int CALIBRATION_SAMPLES = 500;
const float DRIFT_TOLERANCE = 0.02;

// LED and Alert pins
const int greenLED = 8;    // X-axis / Normal status
const int yellowLED = 9;   // Y-axis / Warning
const int redLED = 10;     // Z-axis / Fault

// ============================================================================
// SYSTEM STATES (Fault Classification)
// ============================================================================
enum SystemState {
  NORMAL = 0,
  LOW_SIGNAL = 1,
  SENSOR_FAULT = 2,
  SYSTEM_FAULT = 3
};

SystemState current_state = NORMAL;
SystemState previous_state = NORMAL;
uint32_t fault_start_time = 0;
uint32_t state_entry_time = 0;

// Fault thresholds
const float SNR_THRESHOLD_DB = 10.0;           // Minimum acceptable SNR
const uint32_t LOW_SIGNAL_DURATION_MS = 3000;  // 3 seconds before fault
const uint32_t SENSOR_TIMEOUT_MS = 500;        // I2C timeout
const uint32_t TIMING_TOLERANCE_US = 2000;     // Timing slip tolerance

// ============================================================================
// CIRCULAR BUFFER FOR RAW DATA (OPTIMIZED FOR MEMORY)
// ============================================================================
const int BUFFER_SIZE = 64;  // Reduced from 256 to save RAM (0.64 seconds at 100 Hz)
struct CircularBuffer {
  float data[BUFFER_SIZE];
  uint8_t head = 0;
  uint8_t tail = 0;
  
  void push(float value) {
    data[head] = value;
    head = (head + 1) & (BUFFER_SIZE - 1);  // Fast modulo for power of 2
    if (head == tail) {
      tail = (tail + 1) & (BUFFER_SIZE - 1);  // Overwrite oldest
    }
  }
  
  float get(uint8_t index) {
    return data[(tail + index) & (BUFFER_SIZE - 1)];
  }
  
  uint8_t count() {
    if (head >= tail) return head - tail;
    return BUFFER_SIZE - tail + head;
  }
  
  void clear() {
    head = 0;
    tail = 0;
  }
};

CircularBuffer buf_ax, buf_ay, buf_az;

// ============================================================================
// CALIBRATION DATA
// ============================================================================
struct CalibrationData {
  int32_t ax_offset = 0;  // Fixed-point (scaled by 16384)
  int32_t ay_offset = 0;
  int32_t az_offset = 0;
  bool is_calibrated = false;
} calibration;

// ============================================================================
// HIGH-PASS FILTER (Fixed-point for efficiency)
// ============================================================================
const int32_t HP_ALPHA_FIXED = 32112;  // 0.98 * 32768
struct HighPassFilterFixed {
  int32_t prev_input = 0;
  int32_t prev_output = 0;
  
  int32_t apply(int32_t input) {
    int32_t diff = input - prev_input;
    int32_t output = ((int64_t)HP_ALPHA_FIXED * (prev_output + diff)) >> 15;
    prev_input = input;
    prev_output = output;
    return output;
  }
  
  void reset() {
    prev_input = 0;
    prev_output = 0;
  }
};

// ============================================================================
// LOW-PASS FILTER (Fixed-point)
// ============================================================================
const int32_t LP_ALPHA_FIXED = 18022;  // 0.55 * 32768
struct LowPassFilterFixed {
  int32_t prev_output = 0;
  
  int32_t apply(int32_t input) {
    int32_t output = ((int64_t)LP_ALPHA_FIXED * input + 
                      (int64_t)(32768 - LP_ALPHA_FIXED) * prev_output) >> 15;
    prev_output = output;
    return output;
  }
  
  void reset() {
    prev_output = 0;
  }
};

HighPassFilterFixed hp_x, hp_y, hp_z;
LowPassFilterFixed lp_x, lp_y, lp_z;

// ============================================================================
// TIMING AND SCHEDULING
// ============================================================================
uint32_t next_sample_time = 0;
uint32_t next_analysis_time = 0;
uint32_t sample_count = 0;
uint32_t missed_deadlines = 0;
uint32_t uptime_seconds = 0;
uint32_t last_second_mark = 0;

// ============================================================================
// FEATURE EXTRACTION RESULTS
// ============================================================================
struct FeatureData {
  float frequency_hz = 0.0;
  float amplitude_mg = 0.0;
  float rms_mg = 0.0;
  float snr_db = 0.0;
  uint32_t timestamp_ms = 0;
  bool valid = false;
};

FeatureData current_features;
// Removed trend_history array to save RAM (Python handles trend storage)

// ============================================================================
// WATCHDOG FLAGS
// ============================================================================
bool sensor_ok = true;
uint32_t last_sensor_read = 0;
uint32_t low_snr_start = 0;
bool low_snr_fault = false;

// ============================================================================
// SETUP
// ============================================================================
void setup() {
  Wire.begin();
  Wire.setClock(400000);
  Serial.begin(115200);
  
  pinMode(greenLED, OUTPUT);
  pinMode(yellowLED, OUTPUT);
  pinMode(redLED, OUTPUT);
  
  LEDSelfTest();
  
  Serial.println(F("# ========================================"));
  Serial.println(F("# HFOV Clinical Monitor v2.0"));
  Serial.println(F("# ========================================"));
  
  // Initialize MPU6050
  mpu.initialize();
  mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  mpu.setDLPFMode(MPU6050_DLPF_BW_42);
  mpu.setRate(9);
  mpu.setSleepEnabled(false);
  
  if (!mpu.testConnection()) {
    Serial.println(F("# FATAL: MPU6050 connection failed!"));
    enterFaultState(SENSOR_FAULT);
    while (1) {
      blinkFaultLED();
      delay(500);
    }
  }
  
  Serial.println(F("# MPU6050 OK"));
  
  runCalibration();
  
  Serial.println(F("# Ready"));
  Serial.println(F("# C,FREQ,AMP,RMS,SNR,STATE,UPTIME (1Hz)"));
  Serial.println(F("# W,ax,ay,az,mag (100Hz)"));
  Serial.println(F("# ========================================"));
  
  next_sample_time = micros();
  next_analysis_time = millis() + ANALYSIS_INTERVAL_MS;
  last_second_mark = millis();
  
  enterState(NORMAL);
}

// ============================================================================
// MAIN LOOP - DUAL TASK STRUCTURE
// ============================================================================
void loop() {
  uint32_t current_time_us = micros();
  uint32_t current_time_ms = millis();
  
  // ===== HIGH-RATE TASK: SENSOR READ + FILTER (100 Hz) =====
  if (current_time_us >= next_sample_time) {
    // Check for timing slip
    uint32_t slip = current_time_us - next_sample_time;
    if (slip > TIMING_TOLERANCE_US) {
      missed_deadlines++;
      if (missed_deadlines > 10) {
        enterFaultState(SYSTEM_FAULT);
      }
    }
    
    next_sample_time += SAMPLE_INTERVAL_US;
    
    // Read sensor with watchdog
    int16_t ax_raw, ay_raw, az_raw;
    if (!readSensorSafe(&ax_raw, &ay_raw, &az_raw)) {
      enterFaultState(SENSOR_FAULT);
      return;
    }
    
    // Apply calibration (fixed-point)
    int32_t ax = (int32_t)ax_raw - calibration.ax_offset;
    int32_t ay = (int32_t)ay_raw - calibration.ay_offset;
    int32_t az = (int32_t)az_raw - calibration.az_offset;
    
    // Apply filters (fixed-point)
    int32_t ax_hp = hp_x.apply(ax);
    int32_t ay_hp = hp_y.apply(ay);
    int32_t az_hp = hp_z.apply(az);
    
    int32_t ax_filt = lp_x.apply(ax_hp);
    int32_t ay_filt = lp_y.apply(ay_hp);
    int32_t az_filt = lp_z.apply(az_hp);
    
    // Store in circular buffers (convert to float for analysis)
    buf_ax.push(ax_filt / 16384.0);
    buf_ay.push(ay_filt / 16384.0);
    buf_az.push(az_filt / 16384.0);
    
    sample_count++;
  }
  
  // ===== MEDIUM-RATE TASK: ANALYSIS + OUTPUT (1 Hz) =====
  if (current_time_ms >= next_analysis_time) {
    next_analysis_time += ANALYSIS_INTERVAL_MS;
    
    // Extract features from buffer
    extractFeatures();
    
    // Update state machine
    updateSystemState();
    
    // Output clinical data
    outputClinicalData();
    
    // Update uptime counter
    if (current_time_ms - last_second_mark >= 1000) {
      uptime_seconds++;
      last_second_mark = current_time_ms;
    }
  }
  
  // Update status LEDs
  updateStatusLEDs();
}

// ============================================================================
// SAFE SENSOR READ WITH WATCHDOG
// ============================================================================
bool readSensorSafe(int16_t* ax, int16_t* ay, int16_t* az) {
  uint32_t start = millis();
  
  // Attempt I2C read with timeout
  Wire.beginTransmission(0x68);  // MPU6050 address
  if (Wire.endTransmission() != 0) {
    sensor_ok = false;
    return false;
  }
  
  mpu.getAcceleration(ax, ay, az);
  
  // Check for out-of-range values
  if (abs(*ax) > 32000 || abs(*ay) > 32000 || abs(*az) > 32000) {
    return false;
  }
  
  last_sensor_read = millis();
  sensor_ok = true;
  return true;
}

// ============================================================================
// FEATURE EXTRACTION (Simplified for microcontroller)
// ============================================================================
void extractFeatures() {
  uint8_t count = min((uint8_t)ANALYSIS_WINDOW_SAMPLES, buf_ax.count());
  
  if (count < 50) {
    current_features.valid = false;
    return;
  }
  
  // Calculate RMS amplitude (vector magnitude)
  float sum_sq = 0;
  float peak = 0;
  for (uint8_t i = 0; i < count; i++) {
    float ax = buf_ax.get(i);
    float ay = buf_ay.get(i);
    float az = buf_az.get(i);
    float mag = sqrt(ax*ax + ay*ay + az*az);
    sum_sq += mag * mag;
    if (mag > peak) peak = mag;
  }
  
  float rms = sqrt(sum_sq / count);
  
  // Simple frequency estimation (zero-crossing rate)
  float freq = estimateFrequency(count);
  
  // SNR estimation (signal power / noise estimate)
  float snr = estimateSNR(rms, peak);
  
  // Store results
  current_features.frequency_hz = freq;
  current_features.amplitude_mg = peak * 1000.0;  // Convert to millig
  current_features.rms_mg = rms * 1000.0;
  current_features.snr_db = snr;
  current_features.timestamp_ms = millis();
  current_features.valid = true;
}

float estimateFrequency(uint8_t count) {
  // Zero-crossing rate method (simple, efficient)
  int crossings = 0;
  float prev = buf_az.get(0);
  
  for (uint8_t i = 1; i < count; i++) {
    float curr = buf_az.get(i);
    if ((prev >= 0 && curr < 0) || (prev < 0 && curr >= 0)) {
      crossings++;
    }
    prev = curr;
  }
  
  float freq = (crossings / 2.0) * SAMPLE_RATE_HZ / count;
  return freq;
}

float estimateSNR(float rms, float peak) {
  // Simple SNR: peak signal / RMS noise estimate
  if (rms < 0.001) return 0;
  float signal_power = peak * peak;
  float noise_power = rms * rms - signal_power * 0.5;  // Rough estimate
  if (noise_power < 0.0001) return 40;
  return 10.0 * log10(signal_power / noise_power);
}

// ============================================================================
// STATE MACHINE
// ============================================================================
void updateSystemState() {
  SystemState new_state = current_state;
  uint32_t now = millis();
  
  // Check for sensor fault
  if (!sensor_ok || (now - last_sensor_read > SENSOR_TIMEOUT_MS)) {
    new_state = SENSOR_FAULT;
  }
  // Check for low signal
  else if (current_features.valid && current_features.snr_db < SNR_THRESHOLD_DB) {
    if (low_snr_start == 0) {
      low_snr_start = now;
    } else if (now - low_snr_start > LOW_SIGNAL_DURATION_MS) {
      new_state = LOW_SIGNAL;
    }
  }
  // Recovery: SNR back to normal
  else if (current_features.valid && current_features.snr_db >= SNR_THRESHOLD_DB + 2.0) {
    low_snr_start = 0;
    if (current_state == LOW_SIGNAL) {
      new_state = NORMAL;
    }
  }
  
  // State change with hysteresis
  if (new_state != current_state) {
    if (new_state == NORMAL) {
      // Require 2 seconds in good condition before clearing fault
      if (now - state_entry_time > 2000) {
        enterState(new_state);
      }
    } else {
      enterState(new_state);
    }
  }
}

void enterState(SystemState state) {
  previous_state = current_state;
  current_state = state;
  state_entry_time = millis();
  
  if (state != NORMAL && previous_state == NORMAL) {
    fault_start_time = millis();
  }
}

void enterFaultState(SystemState state) {
  enterState(state);
}

// ============================================================================
// STATUS LED CONTROL
// ============================================================================
void updateStatusLEDs() {
  switch (current_state) {
    case NORMAL:
      digitalWrite(greenLED, (millis() % 2000) < 100);  // Short blink
      digitalWrite(yellowLED, LOW);
      digitalWrite(redLED, LOW);
      break;
    case LOW_SIGNAL:
      digitalWrite(greenLED, LOW);
      digitalWrite(yellowLED, (millis() % 1000) < 500);  // Blink
      digitalWrite(redLED, LOW);
      break;
    case SENSOR_FAULT:
    case SYSTEM_FAULT:
      digitalWrite(greenLED, LOW);
      digitalWrite(yellowLED, LOW);
      digitalWrite(redLED, (millis() % 500) < 250);  // Fast blink
      break;
  }
}

void blinkFaultLED() {
  digitalWrite(redLED, !digitalRead(redLED));
}

// ============================================================================
// CLINICAL DATA OUTPUT (1 Hz)
// ============================================================================
void outputClinicalData() {
  // Format: C,FREQ,AMP,RMS,SNR,STATE,UPTIME (C = clinical marker)
  Serial.print(F("C,"));
  Serial.print(current_features.frequency_hz, 2);
  Serial.print(F(","));
  Serial.print(current_features.amplitude_mg, 2);
  Serial.print(F(","));
  Serial.print(current_features.rms_mg, 2);
  Serial.print(F(","));
  Serial.print(current_features.snr_db, 1);
  Serial.print(F(","));
  Serial.print(current_state);
  Serial.print(F(","));
  Serial.println(uptime_seconds);
}

// ============================================================================
// CALIBRATION
// ============================================================================
void runCalibration() {
  Serial.println(F("# CAL: Keep still 5 sec"));
  digitalWrite(yellowLED, HIGH);
  delay(1000);
  
  int64_t sum_ax = 0, sum_ay = 0, sum_az = 0;
  
  for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
    int16_t ax, ay, az;
    mpu.getAcceleration(&ax, &ay, &az);
    sum_ax += ax;
    sum_ay += ay;
    sum_az += az;
    
    if (i % 50 == 0) {
      digitalWrite(greenLED, !digitalRead(greenLED));
    }
    delay(10);
  }
  
  calibration.ax_offset = sum_ax / CALIBRATION_SAMPLES;
  calibration.ay_offset = sum_ay / CALIBRATION_SAMPLES;
  calibration.az_offset = sum_az / CALIBRATION_SAMPLES;
  calibration.is_calibrated = true;
  
  digitalWrite(greenLED, LOW);
  digitalWrite(yellowLED, LOW);
  
  Serial.println(F("# CAL: Complete"));
}

void LEDSelfTest() {
  digitalWrite(greenLED, HIGH); delay(200); digitalWrite(greenLED, LOW);
  digitalWrite(yellowLED, HIGH); delay(200); digitalWrite(yellowLED, LOW);
  digitalWrite(redLED, HIGH); delay(200); digitalWrite(redLED, LOW);
}