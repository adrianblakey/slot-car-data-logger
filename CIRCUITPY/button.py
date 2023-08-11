
import digitalio
import log
from counter import Counter
import microcontroller
from adafruit_debouncer import Debouncer
import asyncio
import tune
from time import monotonic, monotonic_ns, time, sleep
from ledcontrol import LedControl


class Button:
    """ Represents a button,captures long and short button presses """

    def __init__(self, red_led_control: LedControl, yellow_led_control: LedControl,
                 green_led_control: LedControl,
                 pin: microcontroller.Pin, short_press: float = .3, long_press: float = .5,
                 counter: Counter = Counter()):
        self._red_led_control = red_led_control
        self._yellow_led_control = yellow_led_control
        self._green_led_control = green_led_control
        self._pin = pin
        self._short_press = short_press
        self._long_press = long_press
        self._counter = counter

    @property
    def pin(self) -> microcontroller.Pin:
        return self._pin

    @pin.setter
    def pin(self, pin: microcontroller.Pin):
        self._pin = pin

    @property
    def red_led_control(self) -> LedControl:
        return self._red_led_control

    @red_led_control.setter
    def red_led_control(self, red_led_control: LedControl):
        self._red_led_control = red_led_control

    @property
    def yellow_led_control(self) -> LedControl:
        return self._yellow_led_control

    @yellow_led_control.setter
    def yellow_led_control(self, yellow_led_control: LedControl):
        self._yellow_led_control = yellow_led_control

    @property
    def green_led_control(self) -> LedControl:
        return self._green_led_control

    @green_led_control.setter
    def green_led_control(self, green_led_control: LedControl):
        self._green_led_control = green_led_control

    @property
    def long_press(self) -> float:
        return self._long_press

    @long_press.setter
    def long_press(self, long_press: float):
        self._long_press = long_press

    @property
    def short_press(self) -> float:
        return self._short_press

    @short_press.setter
    def short_press(self, short_press: float):
        self._short_press = short_press

    async def capture(self) -> None:
        """ Capture the button forever.
        """
        # Press button down to increment, long (>1 sec) to leave
        with digitalio.DigitalInOut(self._pin) as b_pin:
            b_pin.direction = digitalio.Direction.INPUT
            b_pin.pull = digitalio.Pull.UP
            yellow_debouncer = Debouncer(b_pin)
            self.counter.short_count = 0
            tick = 0
            while True:
                tick += 1
                if tick == 50000:
                    tune.REMINDER.play()
                    tick = 0
                yellow_debouncer.update()
                if yellow_debouncer.fell:
                    start = monotonic()
                    if log.is_debug:
                        log.logger.debug('button pressed at %s', start)
                    self.counter.short_count += 1
                    if self.counter.short_count > self.maximum:  # Reset to 1
                        # flash_led(red_led) TODO write some values to the interval object for the red led
                        tune.LO_HI.play()
                        self.counter.short_count = 1
                    if log.is_debug:
                        log.logger.debug('count: %s', self.counter.short_count)
                elif yellow_debouncer.rose:
                    elapse = monotonic() - start
                    if log.is_debug:
                        log.logger.debug('button released, duration: %s %s', yellow_debouncer.current_duration,
                                             elapse)
                    if elapse <= self.short_press:  # Short press < .4 sec, good count
                        tune.INPUT.play()
                        # flash_led(yellow_led) TODO write values to yellow led
                    else:  # Long press, decrement the count and leave only if > min
                        self.counter.short_count -= 1
                        if log.is_debug:
                            log.logger.debug("long press leave with the number if it's big enough %s %s",
                                              self.counter.short_count, self.minimum)
                        if self.counter.short_count >= self.minimum:
                            [tune.FEEDBACK.play() for _ in range(self.counter.short_count)]  # confirm with beeps
                            #flash_led(yellow_led)
                            return self.counter.short_count
                        else:
                            times = self.minimum - self.counter.short_count
                            #flash_led(red_led)
                            tune.HI_LO.play()
                else:
                    pass

