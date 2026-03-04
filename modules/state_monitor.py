# modules/state_monitor.py
import time
from rtma.messages import SNRMsg, AccelMsg, StateMsg

# State constants — mirror the reference LivePlot_V9 values
STATE_NORMAL     = 0
STATE_LOW_SIGNAL = 1
STATE_FAULT      = 2


class StateMonitor:
    """
    Derives the system state from SNR quality and data-timeout detection,
    then publishes a StateMsg on every SNR update.

    Rules (match LivePlot_V9):
      - FAULT       : no AccelMsg received for > FAULT_TIMEOUT seconds
      - LOW_SIGNAL  : SNR < snr_threshold_db
      - NORMAL      : otherwise
    """

    FAULT_TIMEOUT    = 3.0   # seconds without data → FAULT
    SNR_THRESHOLD_DB = 10.0  # matches LivePlot_V9 reference

    def __init__(self, bus):
        self.bus = bus
        self._last_data_time = time.monotonic()
        self._current_snr    = None

        bus.subscribe(AccelMsg, self._on_accel)
        bus.subscribe(SNRMsg,   self._on_snr)

    # ------------------------------------------------------------------
    def _on_accel(self, msg: AccelMsg):
        """Keep the data-watchdog alive."""
        self._last_data_time = time.monotonic()

    def _on_snr(self, msg: SNRMsg):
        self._current_snr = msg.snr_db
        state = self._compute_state()
        self.bus.publish(StateMsg(state=state))

    # ------------------------------------------------------------------
    def _compute_state(self) -> int:
        elapsed_since_data = time.monotonic() - self._last_data_time

        if elapsed_since_data > self.FAULT_TIMEOUT:
            return STATE_FAULT

        if self._current_snr is not None and self._current_snr < self.SNR_THRESHOLD_DB:
            return STATE_LOW_SIGNAL

        return STATE_NORMAL