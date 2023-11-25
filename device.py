# Copyright @ 20023, Adrian Blakey. All rights reserved
# Represents the logger hardware

from machine import ADC, Pin
import logging
import time
import random
import math

global the_device   # imported into main

log = logging.getLogger("device")

SF: float = 17.966 / 3.3   # Scaling
CF: float = 3.3 / 65535    # Conversion factor

divisor: int = 4

class Device():
    
    def __init__(self):
        self._zero_current: int = 0
        self._adc0 = ADC(Pin(26))
        self._adc1 = ADC(Pin(27))
        self._adc2 = ADC(Pin(28))
        self._adc_filtered: float = 0
        # Pin 29 our supply voltage
        
    def calibrate_current(self) -> None:
        # Measure the current 10 times and average
        i = 0
        count: int = 0
        while i < 10:
            count += self._adc0.read_u16()
            i += 1
        self._zero_current = round(count / 10)
        log.debug('Calibrated current raw u_16 value %s', self._zero_current)

    def filter(self, value: float) -> float:
        self._adc_filtered = self._adc_filtered + value - (self._adc_filtered / divisor)
        return self._adc_filtered / divisor
        
    def __current(self) -> float:
        # Scale the current
        return (self._adc0.read_u16() - self._zero_current) * CF / .025  # ~1.65 = 0 point, .025 = 1 amp
    
    def read_all(self) -> str:
        return f"{str(time.time_ns())[:-6]},{self._adc2.read_u16() * CF * SF:.6f},{self._adc1.read_u16() * CF * SF:.6f},{self.__current():.6f}"
    
    def read(self) -> str:
        return f"{self._adc2.read_u16() * CF * SF:.6f},{self._adc1.read_u16() * CF * SF:.6f},{self.__current():.6f}"
try:
    the_device
except NameError:
    log.info('the_device not yet defined')
    the_device = Device()
    the_device.calibrate_current()
        
if __name__ == "__main__":
    print(the_device.read_all())





