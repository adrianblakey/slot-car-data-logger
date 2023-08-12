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

"""

import microcontroller
from statemachine import StateMachine
import log
from time import sleep

if log.is_debug:
    debug = True
else:
    debug = False


def main():
    sm = StateMachine()
    sm.run()            # Run the state machine - that's it


print()                 # Stupid REPL id does not end with a \n
try:
    if log.is_debug:
        log.logger.debug("%s Run main", __file__)
    main()
except Exception as e:
    if log.is_debug:
        log.logger.debug("%s Run main. Exception: %s", __file__, e)
        log.logger.debug("%s Resetting mcu in 5 seconds", __file__)
    sleep(5)
    microcontroller.reset()



