"""Module: accel_msg
Role: Accelerometer sample message
"""

class AccelMsg:
    def __init__(self, t, ax, ay, az):
        self.t = t
        self.ax = ax
        self.ay = ay
        self.az = az

    def to_dict(self):
        return self.__dict__
