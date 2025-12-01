#include <Wire.h>
#include <MPU6050.h>

MPU6050 mpu;

// LED pins
const int redLED = 8;
const int greenLED = 9;
const int blueLED = 10;

// Calibration offsets
int16_t ax_offset = 0, ay_offset = 0, az_offset = 0;

// Threshold (g)
const float THRESHOLD = 0.50;

unsigned long lastTime = 0;

void setup() {
  Wire.begin();
  Serial.begin(115200);

  mpu.initialize();
  mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
  mpu.setDLPFMode(MPU6050_DLPF_BW_20);

  pinMode(redLED, OUTPUT);
  pinMode(greenLED, OUTPUT);
  pinMode(blueLED, OUTPUT);

  LEDSelfTest();

  while (!mpu.testConnection());

  while (!Serial.available());
  while (Serial.available()) Serial.read();

  calibrateMPU();

  // CSV header for Python
  Serial.println("Time_ms,Ax,Ay,Az,Magnitude");
}

void loop() {
  unsigned long now = millis();

  // read accel
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);

  // deviation after calibration
  float dx = abs((ax - ax_offset) / 16384.0);
  float dy = abs((ay - ay_offset) / 16384.0);
  float dz = abs((az - az_offset) / 16384.0);

  // LED logic
  digitalWrite(redLED,   dx > THRESHOLD);
  digitalWrite(greenLED, dy > THRESHOLD);
  digitalWrite(blueLED,  dz > THRESHOLD);

  // compute magnitude (raw accelerometer magnitude)
  float magnitude = sqrt((long)ax * ax + (long)ay * ay + (long)az * az);

  // ---- CSV output for Python ----
  Serial.print(now); Serial.print(",");
  Serial.print(ax);  Serial.print(",");
  Serial.print(ay);  Serial.print(",");
  Serial.print(az);  Serial.print(",");
  Serial.println(magnitude);

  delay(10); // ~100 Hz
}

// ---- FUNCTIONS ----

void calibrateMPU() {
  long ax_sum = 0, ay_sum = 0, az_sum = 0;

  for (int i = 0; i < 200; i++) {
    int16_t ax, ay, az;
    mpu.getAcceleration(&ax, &ay, &az);
    ax_sum += ax;
    ay_sum += ay;
    az_sum += az;
    delay(5);
  }

  ax_offset = ax_sum / 200;
  ay_offset = ay_sum / 200;
  az_offset = az_sum / 200;
}

void LEDSelfTest() {
  digitalWrite(redLED, HIGH); delay(200); digitalWrite(redLED, LOW);
  digitalWrite(greenLED, HIGH); delay(200); digitalWrite(greenLED, LOW);
  digitalWrite(blueLED, HIGH); delay(200); digitalWrite(blueLED, LOW);
}
