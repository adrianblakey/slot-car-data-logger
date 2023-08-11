# Copyright @ 2023 Adrian Blakey, All rights reserved.

"""

Slot car data logger firmware.

Channels:

  GP17      - External red LED, low ON
  GP18      - External yellow LED, low = ON
  GP16      - Push button black
  GP21      - Piezo
  GP22      - Push button - yellow
  GP26/ADC0 - Current drawn by the motor through the hand controller
  GP27/ADC1 - Output voltage to track and motor from the hand controller
  GP28/ADC2 - Track incoming supply voltage

TODO
Configure from a track server to an http query
Javascript in a file
Use a different/better chart lib
Async io for the input
"""

import board
from ledcontrol import LedControl
from led import Led
from statemachine import StateMachine
from calibration import Calibration
import states
import log
from track import Track


if log.is_debug:
    debug = True
else:
    debug = False


def main():
    red_led_control = LedControl('red', state='off')
    yellow_led_control = LedControl('yellow', state='off')
    green_led_control = LedControl('green', state='off')
    red_led = Led(pin=board.GP17, led_control=red_led_control, on_value=False)
    yellow_led = Led(pin=board.GP18, led_control=yellow_led_control, on_value=False)
    green_led = Led(pin=board.LED, led_control=green_led_control, on_value=True)
    # red_led_task = asyncio.create_task(red_led.blink())
    # yellow_led_task = asyncio.create_task(yellow_led.blink())
    # green_led_task = asyncio.create_task(green_led.blink())

    sm = StateMachine(red_led, yellow_led, green_led, red_led_control, yellow_led_control, green_led_control,
                      Calibration(),
                      Track(),
                      states.STATES)
    sm.run()
    # sm_task = asyncio.create_task(sm.run())
    # await asyncio.gather(red_led_task, yellow_led_task, green_led_task, sm_task)


print()
if log.is_debug:
    log.logger.debug("%s Run main", __file__)
main()





