
import log
import tune
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

    def __init__(self, red_led: Led, yellow_led: Led, green_led: Led, red_led_control: LedControl,
                 yellow_led_control: LedControl,
                 green_led_control: LedControl, calibration: Calibration, track: Track, states: list, state: int = 0,
                 ):
        self._red_led = red_led
        self._yellow_led = yellow_led
        self._green_led = green_led
        self._red_led_control = red_led_control
        self._yellow_led_control = yellow_led_control
        self._green_led_control = green_led_control
        self._calibration = calibration
        self._track = track
        self._states = states
        self._state = state

    @property
    def calibration(self) -> Calibration:
        return self._calibration

    @calibration.setter
    def calibration(self, calibration: int):
        self._calibration = calibration

    def flash_start(self):
        if log.is_debug:
            log.logger.debug("%s Running init confirmation", __file__)
        tune.START_UP.play()
        if log.is_debug:
            log.logger.debug("%s Flash leds", __file__)

        self._red_led_control.state = 'flash'
        self._red_led_control.reps = 2
        self._red_led_control.on_time = .5
        self._red_led_control.off_time = .5
        self._yellow_led_control.state = 'flash'
        self._yellow_led_control.reps = 2
        self._yellow_led_control.on_time = .5
        self._yellow_led_control.off_time = .5
        self._green_led_control.state = 'flash'
        self._green_led_control.reps = 2
        self._green_led_control.on_time = .5
        self._green_led_control.off_time = .5

        self._red_led.control()
        self._yellow_led.control()
        self._green_led.control()

    def calibrate(self):
        if log.is_debug:
            log.logger.debug("%s Running calibrate method", __file__)
        self.calibration.zero_current = functions.calibrate_current()

    def connect_to_wifi(self):
        """ Can throw runtime """
        global ssid
        global ip
        if log.is_debug:
            log.logger.debug("%s Running connect to wifi method", __file__)
        ssid, ip = functions.connect_to_wifi()  # TODO save the return values - or not

    def input_track(self):
        """ Can throw runtime """
        if log.is_debug:
            log.logger.debug("%s Running input track lane count", __file__)
        lanes = functions.input_number(minimum=1, maximum=8)  # TODO save the return values - or not
        self._track.number_of_lanes = lanes
        my_lane = functions.input_number(minimum=1, maximum=lanes)
        self._track.my_lane = my_lane
        lane_colors = Track.TRACK_LANES[lanes]
        self._track.my_lane_color = lane_colors[my_lane - 1]
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
        webserver.run(self.calibration)

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
                x = self.states[self.state]
                x(self)
                self.state += 1
            else:
                break

