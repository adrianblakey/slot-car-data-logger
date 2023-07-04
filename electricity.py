class Electricity(ABC):
    """
    A unified way to collect input - perhaps it's overkill
    
    
    Abstract base class for voltages and current"""
    @abstractmethod
    def value(self) -> int:
        pass

    @abstractmethod
    def value(self, value: int):
        pass


class Voltage(Electricity):
    """ADC read voltage"""
    def __init__(self):
        self.value = 0

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = value


class Current(Electricity):
    """ADC read current"""
    def __init__(self):
        self.value = 0

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = value

