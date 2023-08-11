
import log


class LedControl:
    """ State - on/off/flash, on time, off time, number of reps. """

    def __init__(self, color: str, state: str = 'off', on_time: float = 0.5, off_time: float = 0.5, reps: int = 3):
        self._color = color
        self._state = state
        self._on_time = on_time
        self._off_time = off_time
        self._reps = reps

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, color: str):
        self._color = color.lower()

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, state: str):
        self._state = state.lower()

    @property
    def on_time(self) -> float:
        return self._on_time

    @on_time.setter
    def on_time(self, on_time: float):
        self._on_time = on_time

    @property
    def off_time(self) -> float:
        return self._off_time

    @off_time.setter
    def off_time(self, off_time: float):
        self._off_time = off_time

    @property
    def reps(self) -> int:
        return self._reps

    @reps.setter
    def reps(self, reps: int):
        self._reps = reps
