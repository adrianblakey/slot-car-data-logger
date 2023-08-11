

class Counter:
    """ Button press counter """

    def __init__(self, short_count: int = 0, long_count: int = 0, minimum: int = 1, maximum: int = 8):
        self._short_count = short_count
        self._long_count = long_count
        self._minimum = minimum
        self._maximum = maximum

    @property
    def short_count(self) -> int:
        return self._short_count

    @short_count.setter
    def short_count(self, short_count: int):
        self._short_count = short_count

    @property
    def long_count(self) -> int:
        return self.long_count

    @long_count.setter
    def long_count(self, long_count: int):
        self._long_count = long_count

    @property
    def minimum(self) -> int:
        return self.minimum

    @minimum.setter
    def minimum(self, minimum: int):
        self._minimum = minimum

    @property
    def maximum(self) -> int:
        return self.maximum

    @maximum.setter
    def maximum(self, maximum: int):
        self._maximum = maximum
