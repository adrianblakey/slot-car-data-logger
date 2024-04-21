# Copyright @ 2023, Adrian Blakey. All rights reserved
# Our leds
from machine import Pin
import logging


log = logging.getLogger("led")

class Led():
      
    def __init__(self, pin: Pin, pullup: bool = False, pulldown: bool = False):
        self._pin: Pin = pin
        if pulldown:
            _pull: int = Pin.PULL_UP
        elif pullup:
            _pull: int = Pin.PULL_DOWN
        else:
            _pull: int = None
        self._pin = Pin(pin, mode = Pin.OUT, pull = _pull)
        self._pin.high()
        
    def on(self):
        self._pin.low()
        
    def off(self):
        self._pin.high()
        
    def toggle(self):
        self._pin.toggle()
        
try:
    yellow_led
except NameError:
    log.info('yellow_led Not yet defined')
    yellow_led = Led(18)
try:
    red_led
except NameError:
    log.info('red_led Not yet defined')
    red_led = Led(17)

