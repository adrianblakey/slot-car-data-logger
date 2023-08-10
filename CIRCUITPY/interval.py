class Interval:
    """ Amount of time to turn on a Led. 0.0 means turn off """

    def __init__(self, value: float = 0.0):
        self._value = value

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = value
