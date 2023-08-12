import board

import log
from ledcontrol import LedControl
from led import Led
import functions
from calibration import Calibration
from track import Track

import gc


ssid = ''
ip = ''


class StateMachine:
    """ Drives the processing """

    def __init__(self):
        self._red_led_control: LedControl = LedControl(color='red', state='flash', on_time=.2, off_time=.2)
        self._yellow_led_control: LedControl = LedControl(color='yellow', state='flash', on_time=.2, off_time=.2)
        self._green_led_control: LedControl = LedControl(color='green', state='flash', on_time=.2, off_time=.2)
        self._red_led = Led(pin=board.GP17, led_control=self._red_led_control, on_value=False)
        self._yellow_led = Led(pin=board.GP18, led_control=self._yellow_led_control, on_value=False)
        self._green_led = Led(pin=board.LED, led_control=self._green_led_control, on_value=True)
        self._calibration: Calibration = Calibration()     # Calibration settings
        self._track: Track = Track()                       # Track we are on
        self._states: list = StateMachine.STATES          # All possible states
        self._state: int = 0                               # Starting state

    def flash_start(self) -> None:
        if log.is_debug:
            log.logger.debug("%s Flash start", __file__)
        functions.flash_start(self._red_led, self._yellow_led, self._green_led)

    def calibrate(self) -> None:
        if log.is_debug:
            log.logger.debug("%s Running calibrate method", __file__)
        self._calibration.zero_current = functions.calibrate_current()

    def connect_to_wifi(self) -> None:
        """ Can throw runtime """
        global ssid
        global ip
        if log.is_debug:
            log.logger.debug("%s Running connect to wifi method", __file__)
        ssid, ip = functions.connect_to_wifi()

    def input_track(self) -> None:
        """ Captures the track details from buttons.
            Can throw runtime """
        if log.is_debug:
            log.logger.debug("%s Running input track lane count", __file__)
        self._track.number_of_lanes = functions.input_number(self._red_led, self._yellow_led,
                                                             minimum=4, maximum=8)
        if log.is_debug:
            log.logger.debug("%s Running input my lane number for %s lane track",
                             __file__, self._track.number_of_lanes)
        self._track.my_lane = functions.input_number(self._red_led, self._yellow_led,
                                                     minimum=1, maximum=self._track.number_of_lanes)
        self._track.my_lane_color = Track.TRACK_LANES[self._track.number_of_lanes][self._track.my_lane - 1]
        if log.is_debug:
            log.logger.debug("%s track %s", __file__, self._track)

    def connect_to_wifi_as_me(self):
        if log.is_debug:
            log.logger.debug("%s Connect to wifi as me", __file__)
        functions.connect_to_wifi_as_me(self._track, ssid, ip)

    def run_server(self):
        if log.is_debug:
            log.logger.debug("%s Run web server", __file__)
            log.logger.debug("mem: %s", gc.mem_free())
        import webserver
        webserver.run(self._calibration)

    @property
    def states(self) -> list:
        return self._states

    @states.setter
    def states(self, states: list):
        self._states = states

    @property
    def state(self) -> int:
        return self._state

    @state.setter
    def state(self, state: int):
        self._state = state

    def run(self):
        while True:
            if self.state < len(self.states):
                fn = self.states[self.state]
                fn(self)
                self.state += 1
            else:
                break

    STATES = [flash_start,
              calibrate,
              connect_to_wifi,
              input_track,
              connect_to_wifi_as_me,
              run_server]