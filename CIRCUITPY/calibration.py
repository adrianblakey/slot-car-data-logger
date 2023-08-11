

class Calibration:
    """ Drives the processing """

    def __init__(self, zero_current: float = 1.65):
        self._zero_current = zero_current

    @property
    def zero_current(self) -> float:
        return self._zero_current

    @zero_current.setter
    def zero_current(self, zero_current: float):
        self._zero_current = zero_current
