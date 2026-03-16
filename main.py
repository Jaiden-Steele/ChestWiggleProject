"""
Module: hfov_main
Role: Main application for HFOV monitoring
"""

import time

from dashboard.rtma_zmq_bridge import RTMAZMQBridge
from rtma.bus import RTMABus
from rtma.recorder import RTMARecorder

from modules.accel_acq import AccelAcq
from modules.digital_filter import DigitalFilter
from modules.frequency_estimator import FrequencyEstimator
from modules.snr_estimator import SNREstimator
from modules.reference_freq import ReferenceFrequency
from modules.frequency_error import FrequencyErrorCalculator

from loggers.frequency_error_logger import FrequencyErrorLogger
from loggers.snr_logger import SNRLogger

bus = RTMABus()
bridge = RTMAZMQBridge(bus, pub_addr="tcp://*:5555")

#  Modules 
acq = AccelAcq(bus)
DigitalFilter(fs=100, bus=bus)
FrequencyEstimator(fs=100, bus=bus)
SNREstimator(fs=100, bus=bus)
FrequencyErrorCalculator(bus)

# Reference frequency source
ref_freq = ReferenceFrequency(bus, f_ref=7.5)  # Hz — can call ref_freq.set_reference(new_f) at runtime to update

#  Loggers (verification artifacts) 
FrequencyErrorLogger(bus, "frequency_error.csv")
SNRLogger(bus, "snr.csv")

#  RTMA recorder (audit + replay) 
recorder = RTMARecorder(bus, "rtma_recording.csv")

print("RTMA system running...")

try:
    while True:
        t = time.time()
        acq.poll()
        ref_freq.update(t)
        time.sleep(0.001)

except KeyboardInterrupt:
    print("Shutting down HFOV monitoring")