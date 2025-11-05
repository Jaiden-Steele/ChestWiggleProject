#include <Wire.h>
#include <MPU6050.h>

// Create MPU6050 object
MPU6050 mpu;

void setup() {
  // Start I2C communication
  Wire.begin();

  // Start serial communication at 115200 baud
  Serial.begin(115200);

  // Initialize MPU6050
  mpu.initialize();
  if (mpu.testConnection()) {
    Serial.println("MPU6050 connected!");
  } else {
    Serial.println("MPU6050 connection failed!");
  }
}

void loop() {
  int16_t ax, ay, az;

  // Read raw acceleration data
  mpu.getAcceleration(&ax, &ay, &az);

  // Print data as CSV: Ax,Ay,Az
  Serial.print(ax); Serial.print(",");
  Serial.print(ay); Serial.print(",");
  Serial.println(az);

  // Short delay to control sampling rate (~100 Hz)
  delay(10);
}
