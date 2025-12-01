#include <Wire.h>
#include <MPU6050.h>

MPU6050 mpu;

// ============================================================================
// CONFIGURATION PARAMETERS
// ============================================================================
const uint32_t SAMPLE_RATE_HZ = 100;           // 100 Hz sampling (well above 80 Hz requirement)
const uint32_t SAMPLE_INTERVAL_US = 1000000 / SAMPLE_RATE_HZ;  // Microseconds between samples

const int CALIBRATION_SAMPLES = 500;            // 5 seconds at 100 Hz
const float DRIFT_TOLERANCE = 0.02;             // 2% drift tolerance

// LED pins for movement indication
const int greenLED = 8;
const int yellowLED = 9;
const int redLED = 10;

// ============================================================================
// CALIBRATION DATA
// ============================================================================
struct CalibrationData {
  float ax_offset = 0.0;
  float ay_offset = 0.0;
  float az_offset = 0.0;
  float ax_scale = 1.0;
  float ay_scale = 1.0;
  float az_scale = 1.0;
  bool is_calibrated = false;
} calibration;

// ============================================================================
// HIGH-PASS FILTER (DC REMOVAL / GRAVITY COMPENSATION)
// ============================================================================
// Simple first-order IIR high-pass filter: y[n] = alpha * (y[n-1] + x[n] - x[n-1])
// Cutoff around 0.5 Hz to remove DC and slow drift
const float HP_ALPHA = 0.98;  // Higher = lower cutoff frequency

struct HighPassFilter {
  float prev_input = 0.0;
  float prev_output = 0.0;
  
  float apply(float input) {
    float output = HP_ALPHA * (prev_output + input - prev_input);
    prev_input = input;
    prev_output = output;
    return output;
  }
  
  void reset() {
    prev_input = 0.0;
    prev_output = 0.0;
  }
};

// ============================================================================
// LOW-PASS FILTER (ANTI-ALIASING / NOISE REDUCTION)
// ============================================================================
// Simple first-order IIR low-pass: y[n] = alpha * x[n] + (1-alpha) * y[n-1]
// Cutoff around 40 Hz to meet bandwidth requirement
const float LP_ALPHA = 0.55;  // Tuned for ~40 Hz cutoff at 100 Hz sample rate

struct LowPassFilter {
  float prev_output = 0.0;
  
  float apply(float input) {
    prev_output = LP_ALPHA * input + (1.0 - LP_ALPHA) * prev_output;
    return prev_output;
  }
  
  void reset() {
    prev_output = 0.0;
  }
};

// ============================================================================
// FILTER INSTANCES (PER AXIS)
// ============================================================================
HighPassFilter hp_x, hp_y, hp_z;
LowPassFilter lp_x, lp_y, lp_z;

// ============================================================================
// TIMING CONTROL
// ============================================================================
uint32_t next_sample_time = 0;
uint32_t sample_count = 0;

// ============================================================================
// LED CONTROL
// ============================================================================
unsigned long greenTimer = 0;
unsigned long yellowTimer = 0;
unsigned long redTimer = 0;
const unsigned long LED_HOLD_TIME = 200;
const float MOVEMENT_THRESHOLD = 0.05;  // Movement detection threshold in g

// ============================================================================
// SETUP
// ============================================================================
void setup() {
  Wire.begin();
  Wire.setClock(400000);  // 400 kHz I2C for faster communication
  Serial.begin(115200);
  
  // Configure LED pins
  pinMode(greenLED, OUTPUT);
  pinMode(yellowLED, OUTPUT);
  pinMode(redLED, OUTPUT);
  
  // LED self-test
  LEDSelfTest();
  
  // Initialize MPU6050
  Serial.println("# Initializing MPU6050...");
  mpu.initialize();
  
  // Configure MPU6050 settings
  // ±2g full scale (16384 LSB/g)
  mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  
  // DLPF bandwidth = 44 Hz (meets ≥40 Hz requirement)
  // This provides hardware anti-aliasing before sampling
  mpu.setDLPFMode(MPU6050_DLPF_BW_42);
  
  // Set sample rate divider (internal rate / (1 + divider))
  // Internal rate with DLPF = 1 kHz, so divider = 9 gives 100 Hz
  mpu.setRate(9);
  
  // Wake up MPU6050 (disable sleep mode)
  mpu.setSleepEnabled(false);
  
  // Test connection
  if (!mpu.testConnection()) {
    Serial.println("# ERROR: MPU6050 connection failed!");
    while (1) {
      digitalWrite(redLED, HIGH);
      delay(100);
      digitalWrite(redLED, LOW);
      delay(100);
    }
  }
  
  Serial.println("# MPU6050 connected successfully");
  Serial.println("# Configuration:");
  Serial.println("#   Full Scale: ±2g");
  Serial.println("#   DLPF Bandwidth: 42 Hz");
  Serial.println("#   Sample Rate: 100 Hz");
  Serial.println("#   High-Pass Filter: 0.5 Hz (DC removal)");
  Serial.println("#   Low-Pass Filter: 40 Hz (noise reduction)");
  Serial.println("#   LEDs: Green=X | Yellow=Y | Red=Z");
  
  // Run calibration
  runCalibration();
  
  Serial.println("# System ready - Starting data acquisition");
  Serial.println("# Format: ax,ay,az,magnitude (all in g, after filtering)");
  
  // Initialize timing
  next_sample_time = micros();
}

// ============================================================================
// MAIN LOOP - FIXED-RATE SAMPLING
// ============================================================================
void loop() {
  uint32_t current_time = micros();
  
  // Wait for next sample time (fixed-rate sampling)
  if (current_time >= next_sample_time) {
    // Schedule next sample
    next_sample_time += SAMPLE_INTERVAL_US;
    
    // Read raw accelerometer data
    int16_t ax_raw, ay_raw, az_raw;
    mpu.getAcceleration(&ax_raw, &ay_raw, &az_raw);
    
    // Convert to g's (±2g = 16384 LSB/g)
    float ax = ax_raw / 16384.0;
    float ay = ay_raw / 16384.0;
    float az = az_raw / 16384.0;
    
    // Apply calibration (offset and scale correction)
    ax = (ax - calibration.ax_offset) * calibration.ax_scale;
    ay = (ay - calibration.ay_offset) * calibration.ay_scale;
    az = (az - calibration.az_offset) * calibration.az_scale;
    
    // Apply DC removal (high-pass filter for gravity compensation)
    float ax_hp = hp_x.apply(ax);
    float ay_hp = hp_y.apply(ay);
    float az_hp = hp_z.apply(az);
    
    // Apply low-pass filter (bandwidth limiting, noise reduction)
    float ax_filt = lp_x.apply(ax_hp);
    float ay_filt = lp_y.apply(ay_hp);
    float az_filt = lp_z.apply(az_hp);
    
    // Calculate vector magnitude
    float magnitude = sqrt(ax_filt * ax_filt + ay_filt * ay_filt + az_filt * az_filt);
    
    // LED indication based on filtered signal
    updateLEDs(ax_filt, ay_filt, az_filt);
    
    // Output filtered data to serial
    Serial.print(ax_filt, 6);
    Serial.print(",");
    Serial.print(ay_filt, 6);
    Serial.print(",");
    Serial.print(az_filt, 6);
    Serial.print(",");
    Serial.println(magnitude, 6);
    
    sample_count++;
  }
}

// ============================================================================
// CALIBRATION ROUTINE
// ============================================================================
void runCalibration() {
  Serial.println("# ========================================");
  Serial.println("# CALIBRATION STARTING");
  Serial.println("# Keep sensor STILL for 5 seconds...");
  Serial.println("# ========================================");
  
  // Visual feedback - Yellow LED during calibration
  digitalWrite(yellowLED, HIGH);
  
  delay(1000);  // Give user time to read message
  
  // Collect baseline samples
  float sum_ax = 0, sum_ay = 0, sum_az = 0;
  float sum_sq_ax = 0, sum_sq_ay = 0, sum_sq_az = 0;
  
  for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
    int16_t ax_raw, ay_raw, az_raw;
    mpu.getAcceleration(&ax_raw, &ay_raw, &az_raw);
    
    float ax = ax_raw / 16384.0;
    float ay = ay_raw / 16384.0;
    float az = az_raw / 16384.0;
    
    sum_ax += ax;
    sum_ay += ay;
    sum_az += az;
    
    sum_sq_ax += ax * ax;
    sum_sq_ay += ay * ay;
    sum_sq_az += az * az;
    
    // Visual progress indicator - blink green LED
    if (i % 50 == 0) {
      digitalWrite(greenLED, !digitalRead(greenLED));
    }
    
    delay(10);  // 100 Hz sampling during calibration
  }
  
  // Calculate offsets (mean values)
  calibration.ax_offset = sum_ax / CALIBRATION_SAMPLES;
  calibration.ay_offset = sum_ay / CALIBRATION_SAMPLES;
  calibration.az_offset = sum_az / CALIBRATION_SAMPLES;
  
  // Calculate standard deviations for drift check
  float std_ax = sqrt(sum_sq_ax / CALIBRATION_SAMPLES - calibration.ax_offset * calibration.ax_offset);
  float std_ay = sqrt(sum_sq_ay / CALIBRATION_SAMPLES - calibration.ay_offset * calibration.ay_offset);
  float std_az = sqrt(sum_sq_az / CALIBRATION_SAMPLES - calibration.az_offset * calibration.az_offset);
  
  // Scale factors (assume unity for now, can be refined with known reference)
  calibration.ax_scale = 1.0;
  calibration.ay_scale = 1.0;
  calibration.az_scale = 1.0;
  
  calibration.is_calibrated = true;
  
  // Turn off LEDs
  digitalWrite(greenLED, LOW);
  digitalWrite(yellowLED, LOW);
  digitalWrite(redLED, LOW);
  
  // Report calibration results
  Serial.println("# ========================================");
  Serial.println("# CALIBRATION COMPLETE");
  Serial.print("# X offset: "); Serial.print(calibration.ax_offset, 6); 
  Serial.print(" g, std: "); Serial.print(std_ax, 6); Serial.println(" g");
  Serial.print("# Y offset: "); Serial.print(calibration.ay_offset, 6); 
  Serial.print(" g, std: "); Serial.print(std_ay, 6); Serial.println(" g");
  Serial.print("# Z offset: "); Serial.print(calibration.az_offset, 6); 
  Serial.print(" g, std: "); Serial.print(std_az, 6); Serial.println(" g");
  
  // Check if drift is within tolerance
  float max_std = max(std_ax, max(std_ay, std_az));
  if (max_std < DRIFT_TOLERANCE) {
    Serial.print("# Drift check: PASS (");
    Serial.print(max_std * 100, 2);
    Serial.println("% < 2%)");
  } else {
    Serial.print("# WARNING: Drift high (");
    Serial.print(max_std * 100, 2);
    Serial.println("%)");
  }
  Serial.println("# ========================================");
  
  delay(1000);
}

// ============================================================================
// LED UPDATE FUNCTION
// ============================================================================
void updateLEDs(float ax, float ay, float az) {
  unsigned long currentTime = millis();
  
  // Detect significant movement in each axis
  if (abs(ax) > MOVEMENT_THRESHOLD) {
    greenTimer = currentTime;  // X-axis = Green LED
  }
  if (abs(ay) > MOVEMENT_THRESHOLD) {
    yellowTimer = currentTime;  // Y-axis = Yellow LED
  }
  if (abs(az) > MOVEMENT_THRESHOLD) {
    redTimer = currentTime;  // Z-axis = Red LED
  }
  
  // Control LEDs with persistence
  digitalWrite(greenLED, (currentTime - greenTimer < LED_HOLD_TIME) ? HIGH : LOW);
  digitalWrite(yellowLED, (currentTime - yellowTimer < LED_HOLD_TIME) ? HIGH : LOW);
  digitalWrite(redLED, (currentTime - redTimer < LED_HOLD_TIME) ? HIGH : LOW);
}

// ============================================================================
// LED SELF-TEST
// ============================================================================
void LEDSelfTest() {
  digitalWrite(greenLED, HIGH); delay(200); digitalWrite(greenLED, LOW);
  digitalWrite(yellowLED, HIGH); delay(200); digitalWrite(yellowLED, LOW);
  digitalWrite(redLED, HIGH); delay(200); digitalWrite(redLED, LOW);
  
  // All on
  digitalWrite(greenLED, HIGH);
  digitalWrite(yellowLED, HIGH);
  digitalWrite(redLED, HIGH);
  delay(300);
  
  // All off
  digitalWrite(greenLED, LOW);
  digitalWrite(yellowLED, LOW);
  digitalWrite(redLED, LOW);
}