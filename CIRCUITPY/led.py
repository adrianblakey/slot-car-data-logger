import digitalio
from interval import Interval
import microcontroller
import asyncio

class Led:
    """ Represents a led, value is the on/off direction, initialized to off
        the board led is pull up, the other 2 are pull down where False is on """

    def __init__(self, pin: microcontroller.Pin, interval: Interval, value: bool = True):
        self._interval = interval
        self._pin = pin
        self._value = value

    @property
    def interval(self) -> Interval:
        return self._interval

    @interval.setter
    def interval(self, interval: Interval):
        self._interval = interval

    @property
    def pin(self) -> microcontroller.Pin:
        return self._pin

    @pin.setter
    def pin(self, pin: microcontroller.Pin):
        self._pin = pin

    @property
    def value(self) -> bool:
        return self._value

    @value.setter
    def value(self, value: bool):
        self._value = value

    async def blink(self) -> None:
        """ Blink the led forever.
        The blinking rate is controlled by the supplied Interval object.
        """
        with digitalio.DigitalInOut(self._pin) as led:
            led.switch_to_output()
            while True:
                led.value = not led.value
                try:
                    await asyncio.sleep(self._interval.value)
                except asyncio.CancelledError as e:
                    if debug:
                        print(f'DEBUG - received request to cancel with: {e}')