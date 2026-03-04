# modules/reference_freq.py
import time
from rtma.messages import ReferenceFreqMsg


class ReferenceFrequency:
    """
    Holds a static reference frequency and publishes it to the bus
    immediately on construction (so FrequencyErrorCalculator has a
    reference from the start) and whenever update() is called.
    """

    def __init__(self, bus, f_ref: float):
        self.bus   = bus
        self.f_ref = f_ref

        # Publish immediately so downstream modules don't wait
        self._publish(time.monotonic())

    # ------------------------------------------------------------------
    def update(self, t=None):
        """Call from your main loop if the reference can change at runtime."""
        self._publish(t if t is not None else time.monotonic())

    def set_reference(self, f_ref: float):
        """Change the reference frequency and broadcast the update."""
        self.f_ref = f_ref
        self.update()

    # ------------------------------------------------------------------
    def _publish(self, t: float):
        self.bus.publish(ReferenceFreqMsg(t=t, f_ref=self.f_ref))