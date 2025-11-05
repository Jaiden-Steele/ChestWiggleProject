# Chest Wiggle Project

**HFOV Chest Wiggle Simulator & Detection Device**  

This project is a prototype system designed to simulate and detect chest wall oscillations for HFOV (High-Frequency Oscillatory Ventilation) research. It consists of:

- **Chest Wiggle Simulator:** 4 small solenoids controlled by an Arduino UNO R3, used to vibrate a tight fabric to simulate chest movement.
- **Chest Wiggle Detection Device:** Wearable accelerometer module (e.g., MPU6050) to monitor chest wall oscillations.

---

## **Hardware**

- Arduino UNO R3
- 4 Small Push-Pull Solenoids (12V DC)
- 2N3904 NPN Transistors
- 1kΩ Resistors
- 1N4001 Diodes
- Breadboard and jumper wires
- External 12V power supply
- Accelerometer module (MPU6050 or ADXL345)
- Arduino-compatible chest strap or fabric for mounting sensors

---

## **Arduino Code**

- The **ChestWiggleReader.ino** sketch reads accelerometer data in real time and prints CSV-formatted values to the Serial Monitor.  
- The **ChestWiggleSimulator.ino** sketch controls the 4 solenoids to produce timed vibration patterns.  

**Dependencies:**

- `Wire.h` (built-in)
- `MPU6050.h` library (install via Arduino Library Manager)

---

## **Getting Started**

1. Install the Arduino IDE: [https://www.arduino.cc/en/software](https://www.arduino.cc/en/software)  
2. Connect your Arduino and select the correct board and COM port.  
3. Install the **MPU6050 library** via Sketch → Include Library → Manage Libraries…  
4. Open the `.ino` file in the Arduino IDE and upload.  
5. Open the Serial Monitor at 115200 baud to view accelerometer data.  

---

## **Future Work**

- Implement real-time plotting and analysis in Python to calculate a “wiggle factor.”  
- Integrate chest wiggle simulation and detection in a closed-loop system.  
- Expand to multiple sensors for more detailed chest wall mapping.  

---

## **License**

This project is open source under the MIT License.
