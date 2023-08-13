# Copyright @ 2023 Adrian Blakey, All rights reserved.

import analogio
import board
from adafruit_httpserver import SSEResponse
from time import monotonic, monotonic_ns
import log
from calibration import Calibration

SF: float = 17.966 / 3.3


class ConnectedClient:

    def __init__(self, response: SSEResponse = None):
        self._calibration = None
        self._response = response
        self._next_message = 0
        self._collected = 0

    @property
    def calibration(self) -> Calibration:
        return self._calibration

    @calibration.setter
    def calibration(self, calibration: int):
        self._calibration = calibration

    @property
    def response(self) -> SSEResponse:
        return self._response

    @response.setter
    def response(self, response: int):
        self._response = response

    @property
    def next_message(self) -> int:
        return self._next_message

    @next_message.setter
    def next_message(self, value: int):
        self._next_message = value

    @property
    def ready(self):
        return self._response and self._next_message < monotonic()

    @property
    def collected(self):
        return self._collected

    @collected.setter
    def collected(self, value: int):
        self._collected = value

    def __scale(self, input_signal: float) -> float:
        """ Scale the current """
        return (input_signal - self.calibration.zero_current) / .025  # ~1.65 = 0 point, .025 = 1 amp

    def send_message(self):
        mark = '0'
        if self._collected > 0:
            mark = '1'
            self._collected = 0
        with analogio.AnalogIn(board.GP26) as cI, \
                analogio.AnalogIn(board.GP27) as cV, \
                analogio.AnalogIn(board.GP28) as tV:
            # Track voltage, controller voltage, controller current
            log.logger.debug("%s Track v: %d normal: %4.4f scaled: %4.4f",
                             __file__,
                             tV.value, (tV.value * 3.3) / 65536, ((tV.value * 3.3) / 65536) * SF)
            self._response.send_event(
                f"{monotonic_ns()},{((tV.value * 3.3) / 65536) * SF},{((cV.value * 3.3) / 65536) * SF},{self.__scale((cI.value * 3.3) / 65536)},{mark}")
        self._next_message = monotonic() + .2
        # board_led.value = not board_led.value
