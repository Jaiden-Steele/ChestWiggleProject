# rtma/messages/filtered_accel_msg.py
import numpy as np


class FilteredAccelMsg:
    """
    Carries the full filtered, projected acceleration window (numpy array).

    to_dict() converts the array to a plain Python list so the ZMQ bridge
    can JSON-serialise it without crashing.
    """

    def __init__(self, t, value):
        self.t     = float(t)
        # Accept both numpy arrays and plain lists/scalars
        self.value = value

    def to_dict(self):
        v = self.value
        # Convert numpy array → plain list for JSON serialisation
        if isinstance(v, np.ndarray):
            v = v.tolist()
        elif hasattr(v, "tolist"):
            v = v.tolist()
        return {"t": self.t, "value": v}