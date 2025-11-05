#include <Wire.h>
#include <MPU6050.h>

MPU6050 mpu;

// LED pins
const int redLED = 8;    // Forward/back  // UP DOWN = AXIAL
const int greenLED = 9;  // Side tilt ACROSS CHEST = SAGITTAL
const int blueLED = 10;  // Up/down AWAY & TOWARDS = CORONAL

// Calibration offsets
int16_t ax_offset = 0, ay_offset = 0, az_offset = 0;

// Deviation threshold (g)
const float THRESHOLD = .50; // Adjust sensitivity

void setup() {
  Wire.begin();
  Serial.begin(115200);
  mpu.initialize();
  mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  mpu.setDLPFMode(MPU6050_DLPF_BW_20);

  pinMode(redLED, OUTPUT);
  pinMode(greenLED, OUTPUT);
  pinMode(blueLED, OUTPUT);

  // Test LEDs at startup
  LEDSelfTest();

  if (!mpu.testConnection()) {
    Serial.println("# MPU6050 connection failed!");
    while (1);
  }

  Serial.println("# MPU6050 connected!");
  Serial.println("# Press any key to calibrate baseline...");
  while (!Serial.available()); // Wait for Serial input
  while (Serial.available()) Serial.read(); // Clear buffer

  calibrateMPU();
  Serial.println("# Calibration complete!");
  Serial.println("# Move the sensor and watch LED responses");
  Serial.println("# ΔX, ΔY, ΔZ values printed for debugging");
}

void loop() {
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);

  // Compute absolute deviation from baseline (calibration)
  float dx = abs((ax - ax_offset) / 16384.0);
  float dy = abs((ay - ay_offset) / 16384.0);
  float dz = abs((az - az_offset) / 16384.0);

  // Reset LEDs
  digitalWrite(redLED, LOW);
  digitalWrite(greenLED, LOW);
  digitalWrite(blueLED, LOW);

  // Light LEDs independently if deviation exceeds threshold
  if (dx > THRESHOLD) digitalWrite(redLED, HIGH);
  if (dy > THRESHOLD) digitalWrite(greenLED, HIGH);
  if (dz > THRESHOLD) digitalWrite(blueLED, HIGH);

  // Serial debug output
  Serial.print("ΔX="); Serial.print(dx, 3);
  Serial.print(" ΔY="); Serial.print(dy, 3);
  Serial.print(" ΔZ="); Serial.println(dz, 3);

  delay(20); // ~50 Hz sampling
}

// --- Functions ---

void calibrateMPU() {
  long ax_sum = 0, ay_sum = 0, az_sum = 0;
  int samples = 200;

  Serial.println("# Calibrating... keep sensor still");
  for (int i = 0; i < samples; i++) {
    int16_t ax, ay, az;
    mpu.getAcceleration(&ax, &ay, &az);
    ax_sum += ax;
    ay_sum += ay;
    az_sum += az;
    delay(5);
  }

  // Save baseline values (do NOT subtract 1g)
  ax_offset = ax_sum / samples;
  ay_offset = ay_sum / samples;
  az_offset = az_sum / samples;
}

void LEDSelfTest() {
  Serial.println("# Running LED self-test");
  digitalWrite(redLED, HIGH); delay(300); digitalWrite(redLED, LOW);
  digitalWrite(greenLED, HIGH); delay(300); digitalWrite(greenLED, LOW);
  digitalWrite(blueLED, HIGH); delay(300); digitalWrite(blueLED, LOW);
  delay(300);
  Serial.println("# LED self-test complete");
}
