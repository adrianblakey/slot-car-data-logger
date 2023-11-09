# Copyright @ 2023, Adrian Blakey. All rights reserved
# Our leds
from machine import Pin
import logging


log = logging.getLogger("led")

class Led():
      
    def __init__(self, pin, internal_pullup = False, internal_pulldown = False):
        self.pin_number = pin
        if internal_pulldown:
            self.internal_pull = Pin.PULL_UP
        elif internal_pullup:
            self.internal_pull = Pin.PULL_DOWN
        else:
            self.internal_pull = None
        self.pin = Pin(pin, mode = Pin.OUT, pull = self.internal_pull)
        self.pin.high()
        
    def on(self):
        self.pin.low()
        
    def off(self):
        self.pin.high()
        
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


