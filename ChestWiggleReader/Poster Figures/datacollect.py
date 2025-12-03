import serial
import serial.tools.list_ports
import time
import csv

BAUD = 115200
DURATION = 10

def find_arduino():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if ("Arduino" in p.description or 
            "CH340" in p.description or 
            "USB" in p.description):
            return p.device
    raise Exception("No Arduino detected")

def record_data():
    PORT = find_arduino()
    print(f"Connecting to {PORT}...")

    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)

    filename = "recorded_data.csv"
    f = open(filename, "w", newline="")
    writer = csv.writer(f)

    writer.writerow(["t", "ax", "ay", "az"])

    print(f"Recording for {DURATION} seconds...")
    start = time.time()

    while time.time() - start < DURATION:
        line = ser.readline().decode(errors="ignore").strip()

        if line.count(",") == 2:
            try:
                ax, ay, az = map(float, line.split(","))
                t = time.time() - start
                writer.writerow([t, ax, ay, az])
            except:
                pass

    f.close()
    ser.close()
    print(f"Saved: {filename}")

if __name__ == "__main__":
    record_data()
