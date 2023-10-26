from machine import Pin
import logging
import time
import random

log = logging.getLogger("device")

SF: float = 17.966 / 3.3


class Device():
    
    def __init__(self):
        self._zero_current: float = 0.0
        self._adc0 = Pin(26, Pin.IN, Pin.PULL_UP)
        self._adc1 = Pin(27, Pin.IN, Pin.PULL_UP)
        self._adc2 = Pin(28, Pin.IN, Pin.PULL_UP)
        
    def calibrate_current(self) -> None:
        """ Measure the current 10 times and average """
        i = 0
        count: float = 0.0
        while i < 10:
            count += (self._adc0.value() * 3.3) / 65536
            i += 1
        self._zero_current = count / 10

    def __current(self) -> float:
        """ Scale the current """
        return (((self._adc0.value() * 3.3) / 65536) - self._zero_current) / .025  # ~1.65 = 0 point, .025 = 1 amp
    
    def read_all(self) -> str:
        cv = ((self._adc1.value() * 3.3) / 65536) * SF
        tv = ((self._adc2.value() * 3.3) / 65536) * SF
        return f"{tv:.3f},{cv:.3f},{self.__current():.3f}"
        
        
try:
    the_device
except NameError:
    log.info('the_device not yet defined')
    the_device = Device()
    the_device.calibrate_current()

#print(the_device.read_all())
