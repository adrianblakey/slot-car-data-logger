import digitalio

import log
from ledcontrol import LedControl
import microcontroller
from time import sleep


class Led:
    """ Represents a led, value is the on/off direction, initialized to off
        the board led is pull up, the other 2 are pull down where False is on """

    def __init__(self, pin: microcontroller.Pin, led_control: LedControl, on_value: bool = True):
        self._led_control = led_control
        self._pin = pin
        self._on_value = on_value

    @property
    def led_control(self) -> LedControl:
        return self._led_control

    @led_control.setter
    def led_control(self, led_control: LedControl):
        self._led_control = led_control

    @property
    def pin(self) -> microcontroller.Pin:
        return self._pin

    @pin.setter
    def pin(self, pin: microcontroller.Pin):
        self._pin = pin

    @property
    def on_value(self) -> bool:
        return self._on_value

    @on_value.setter
    def on_value(self, on_value: bool):
        self._on_value = on_value

    def control(self):
        with digitalio.DigitalInOut(self._pin) as led:
            led.switch_to_output()
            if self.led_control.state == 'on':
                if log.is_debug:
                    log.logger.debug("%s Led on", __file__)
                led.value = self.on_value
            elif self.led_control.state == 'off':
                led.value = not self.on_value
            else:  # self.led_control.state == 'flash':
                if log.is_debug:
                    log.logger.debug("%s Led flash %s, reps: %s on value: %s on time: %4.2f off time: %4.2f", __file__,
                                     self.led_control.color,
                                     self.led_control.reps,
                                     self.on_value, self.led_control.on_time, self.led_control.off_time)
                for _ in range(self.led_control.reps):
                    led.value = self.on_value
                    sleep(self.led_control.on_time)
                    led.value = not self.on_value
                    sleep(self.led_control.off_time)


