
class Calibrate:
    """ Class to hold the state of the modal calibration button.
        Modal:
            Initial state = no calibration
            Current calibration
            Voltage calibration
        """
    # Main modes
    OFF = 0                     # calibration off
    CURRENT = 1                 # current calibration
    VOLTAGE = 2                 # voltage calibration

    # Sub state modes
    WAITING_TO_REMOVE_BLACK = 0
    WAITING_TO_ATTACH_BLACK = 0

    def __init__(self):
        self.calibration = Calibrate.OFF

    def __str__(self) -> str:
        if self.calibration == Calibrate.OFF:
            return "Off"
        elif self.calibration == Calibrate.CURRENT:
            return "Current"
        elif self.calibration == Calibrate.VOLTAGE:
            return "Voltage"

    @property
    def calibration(self) -> int:
        return self._calibration

    @calibration.setter
    def calibration(self, value: int):
        self._calibration = value


    # Bumps the mode up based on current value
    def bump_mode(self):
        if self._calibration == Calibrate.OFF:
            self._calibration = Calibrate.CURRENT
        elif self._calibration == Calibrate.CURRENT:
            self._calibration = Calibrate.VOLTAGE
        elif self._calibration == Calibrate.VOLTAGE:
            self._calibration = Calibrate.OFF

    def is_off(self) -> bool:
        return self._calibration == Calibrate.OFF

    def is_current(self) -> bool:
        return self._calibration == Calibrate.CURRENT

    def is_voltage(self) -> bool:
        return self._calibration == Calibrate.VOLTAGE

