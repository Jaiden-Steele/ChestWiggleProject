#include <Wire.h>
#include <MPU6050.h>

// Create MPU6050 object
MPU6050 mpu;

// Optional: track time in milliseconds
unsigned long lastTime = 0;
const int interval = 10; // 10 ms => ~100 Hz

void setup() {
  Wire.begin();
  Serial.begin(115200);

  mpu.initialize();
  if (mpu.testConnection()) {
    Serial.println("MPU6050 connected!");
  } else {
    Serial.println("MPU6050 connection failed!");
  }

  // Optional: header for CSV
  Serial.println("Time_ms,Ax,Ay,Az,Magnitude");
}

void loop() {
  unsigned long currentTime = millis();
  if (currentTime - lastTime >= interval) {
    lastTime = currentTime;

    int16_t ax, ay, az;
    mpu.getAcceleration(&ax, &ay, &az);

    // Compute magnitude
  float ax_g = ax / 16384.0;
  float ay_g = ay / 16384.0;
  float az_g = az / 16384.0;
  float magnitude = sqrt(ax_g * ax_g + ay_g * ay_g + az_g * az_g);

    // Print CSV: Time, Ax, Ay, Az, Magnitude
    Serial.print(currentTime); Serial.print(",");
    Serial.print(ax); Serial.print(",");
    Serial.print(ay); Serial.print(",");
    Serial.print(az); Serial.print(",");
    Serial.println(magnitude);
  }
}

