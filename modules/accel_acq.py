"""Module: accel_acq
Role: Acquires accelerometer data from serial port
"""

import time, serial, serial.tools.list_ports
from rtma.messages import AccelMsg

class AccelAcq:
    def __init__(self, bus, fs=100):
        self.bus = bus
        self.fs = fs
        self.n = 0
        self.ser = self._connect(115200)

    def _connect(self, baudrate):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            raise RuntimeError("No serial devices found. Is the accelerometer plugged in?")

        port = ports[0].device
        ser = serial.Serial(port, baudrate, timeout=0.01)
        time.sleep(2)
        ser.flushInput()
        return ser

    def step(self):
        while self.ser.in_waiting:
            line = self.ser.readline().decode().strip()
            
            # skip empty lines or comments
            if not line or line.startswith('#'):
                continue
            
            # try to parse numeric data
            try:
                parts = line.split(',')
                if len(parts) != 3:
                    print(f"Skipping line with unexpected format: {line}")
                    continue
                ax, ay, az = map(float, parts)
                msg = AccelMsg(time.monotonic(), ax, ay, az)
                self.n += 1
                return msg
            except ValueError:
                print(f"Skipping non-numeric line: {line}")
                continue

        
    def poll(self):
        msg = self.step()
        if msg:
            self.bus.publish(msg) 
