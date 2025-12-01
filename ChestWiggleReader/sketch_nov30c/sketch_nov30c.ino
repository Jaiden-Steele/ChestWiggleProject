#include <Wire.h>
#include <MPU6050.h>

MPU6050 mpu;

// ============================================================================
// CONFIGURATION
// ============================================================================
const uint32_t SAMPLE_RATE_HZ = 100;
const uint32_t SAMPLE_INTERVAL_US = 10000;  // 10ms = 100 Hz

const int CALIBRATION_SAMPLES = 500;

// LED pins
const int greenLED = 8;
const int yellowLED = 9;
const int redLED = 10;

// ============================================================================
// CALIBRATION
// ============================================================================
int32_t ax_offset = 0;
int32_t ay_offset = 0;
int32_t az_offset = 0;

// ============================================================================
// HIGH-PASS FILTER (DC REMOVAL)
// ============================================================================
const int32_t HP_ALPHA = 32112;  // 0.98 * 32768
struct HPFilter {
  int32_t prev_in = 0;
  int32_t prev_out = 0;
  
  int32_t apply(int32_t input) {
    int32_t diff = input - prev_in;
    int32_t output = ((int64_t)HP_ALPHA * (prev_out + diff)) >> 15;
    prev_in = input;
    prev_out = output;
    return output;
  }
};

// ============================================================================
// LOW-PASS FILTER
// ============================================================================
const int32_t LP_ALPHA = 18022;  // 0.55 * 32768
struct LPFilter {
  int32_t prev_out = 0;
  
  int32_t apply(int32_t input) {
    int32_t output = ((int64_t)LP_ALPHA * input + 
                      (int64_t)(32768 - LP_ALPHA) * prev_out) >> 15;
    prev_out = output;
    return output;
  }
};

HPFilter hp_x, hp_y, hp_z;
LPFilter lp_x, lp_y, lp_z;

// ============================================================================
// TIMING
// ============================================================================
uint32_t next_sample = 0;
uint32_t sample_count = 0;

// ============================================================================
// LED CONTROL
// ============================================================================
unsigned long led_timer[3] = {0, 0, 0};
const unsigned long LED_TIME = 200;
const float MOVE_THRESH = 0.05;

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
  
  // LED test
  digitalWrite(greenLED, HIGH); delay(200); digitalWrite(greenLED, LOW);
  digitalWrite(yellowLED, HIGH); delay(200); digitalWrite(yellowLED, LOW);
  digitalWrite(redLED, HIGH); delay(200); digitalWrite(redLED, LOW);
  
  Serial.println(F("# HFOV Monitor v3.0 - Simplified"));
  
  mpu.initialize();
  mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  mpu.setDLPFMode(MPU6050_DLPF_BW_42);
  mpu.setRate(9);
  mpu.setSleepEnabled(false);
  
  if (!mpu.testConnection()) {
    Serial.println(F("# ERROR: MPU6050 failed"));
    while (1) {
      digitalWrite(redLED, !digitalRead(redLED));
      delay(500);
    }
  }
  
  Serial.println(F("# MPU6050 OK"));
  
  // Calibrate
  Serial.println(F("# Calibrating - keep still 5 sec"));
  digitalWrite(yellowLED, HIGH);
  delay(1000);
  
  int64_t sum_ax = 0, sum_ay = 0, sum_az = 0;
  for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
    int16_t ax, ay, az;
    mpu.getAcceleration(&ax, &ay, &az);
    sum_ax += ax;
    sum_ay += ay;
    sum_az += az;
    if (i % 50 == 0) digitalWrite(greenLED, !digitalRead(greenLED));
    delay(10);
  }
  
  ax_offset = sum_ax / CALIBRATION_SAMPLES;
  ay_offset = sum_ay / CALIBRATION_SAMPLES;
  az_offset = sum_az / CALIBRATION_SAMPLES;
  
  digitalWrite(greenLED, LOW);
  digitalWrite(yellowLED, LOW);
  
  Serial.println(F("# Calibration done"));
  Serial.println(F("# Streaming: ax,ay,az (100 Hz)"));
  Serial.println(F("# ============================"));
  
  next_sample = micros();
}

// ============================================================================
// MAIN LOOP
// ============================================================================
void loop() {
  uint32_t now = micros();
  
  // Fixed-rate sampling at 100 Hz
  if (now - next_sample >= SAMPLE_INTERVAL_US) {
    next_sample = now;
    
    // Read sensor
    int16_t ax_raw, ay_raw, az_raw;
    mpu.getAcceleration(&ax_raw, &ay_raw, &az_raw);
    
    // Apply calibration
    int32_t ax = (int32_t)ax_raw - ax_offset;
    int32_t ay = (int32_t)ay_raw - ay_offset;
    int32_t az = (int32_t)az_raw - az_offset;
    
    // Apply DC removal
    int32_t ax_hp = hp_x.apply(ax);
    int32_t ay_hp = hp_y.apply(ay);
    int32_t az_hp = hp_z.apply(az);
    
    // Apply low-pass filter
    int32_t ax_f = lp_x.apply(ax_hp);
    int32_t ay_f = lp_y.apply(ay_hp);
    int32_t az_f = lp_z.apply(az_hp);
    
    // Convert to g and output
    float ax_g = ax_f / 16384.0;
    float ay_g = ay_f / 16384.0;
    float az_g = az_f / 16384.0;
    
    Serial.print(ax_g, 4);
    Serial.print(F(","));
    Serial.print(ay_g, 4);
    Serial.print(F(","));
    Serial.println(az_g, 4);
    
    // Update LEDs
    unsigned long t = millis();
    if (abs(ax_g) > MOVE_THRESH) led_timer[0] = t;
    if (abs(ay_g) > MOVE_THRESH) led_timer[1] = t;
    if (abs(az_g) > MOVE_THRESH) led_timer[2] = t;
    
    digitalWrite(greenLED, (t - led_timer[0] < LED_TIME) ? HIGH : LOW);
    digitalWrite(yellowLED, (t - led_timer[1] < LED_TIME) ? HIGH : LOW);
    digitalWrite(redLED, (t - led_timer[2] < LED_TIME) ? HIGH : LOW);
    
    sample_count++;
  }
}