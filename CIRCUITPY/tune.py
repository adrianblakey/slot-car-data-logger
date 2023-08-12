
from time import monotonic, monotonic_ns, time, sleep
import board
import pwmio
import log


# Approx Tone frequencies
B0: int = 31
C1: int = 33
CS1: int = 35
D1: int = 37
DS1: int = 39
E1: int = 41
F1: int = 44
FS1: int = 46
G1: int = 49
GS1: int = 52
A1: int = 55
AS1: int = 58
B1: int = 62
C2: int = 65
CS2: int = 69
D2: int = 73
DS2: int = 78
E2: int = 82
F2: int = 87
FS2: int = 93
G2: int = 98
GS2: int = 104
A2: int = 110
AS2: int = 117
B2: int = 123
C3: int = 131
CS3: int = 139
D3: int = 147
DS3: int = 156
E3: int = 165
F3: int = 175
FS3: int = 185
G3: int = 196
GS3: int = 208
A3: int = 220
AS3: int = 233
B3: int = 247
C4: int = 262
CS4: int = 277
D4: int = 294
DS4: int = 311
E4: int = 330
F4: int = 349
FS4: int = 370
G4: int = 392
GS4: int = 415
A4: int = 440
AS4: int = 466
B4: int = 494
C5: int = 523
CS5: int = 554
D5: int = 587
DS5: int = 622
E5: int = 659
F5: int = 698
FS5: int = 740
G5: int = 784
GS5: int = 831
A5: int = 880
AS5: int = 932
B5: int = 988
C6: int = 1047
CS6: int = 1109
D6: int = 1175
DS6: int = 1245
E6: int = 1319
F6: int = 1397
FS6: int = 1480
G6: int = 1568
GS6: int = 1661
A6: int = 1760
AS6: int = 1865
B6: int = 1976
C7: int = 2093
CS7: int = 2217
D7: int = 2349
DS7: int = 2489
E7: int = 2637
F7: int = 2794
FS7: int = 2960
G7: int = 3136
GS7: int = 3322
A7: int = 3520
AS7: int = 3729
B7: int = 3951
C8: int = 4186
CS8: int = 4435
D8: int = 4699
DS8: int = 4978

QUARTER = 4    # Four beats per bar
EIGHT = 8      # 8 beats ...
SIXTEENTH = 16
OCTAVE = 2


class Note:
    """ Played note """
    def __init__(self, tone: int, duration: int = QUARTER) -> None:
        self._tone = tone
        self._duration = duration

    @property
    def tone(self) -> int:
        return self._tone

    @tone.setter
    def tone(self, tone: int):
        self._tone = tone

    @property
    def duration(self) -> int:
        return self._duration

    @duration.setter
    def duration(self, duration: int):
        self._duration = duration


class Tune:
    """ A series of played notes and their durations, played at a specific rate """
    def __init__(self, rate: int = 70, tune: list[Note] = []) -> None:

        self._rate: int = rate
        self._tune: list[Note] = tune

    @property
    def rate(self) -> int:
        return self._rate

    @rate.setter
    def rate(self, rate: int):
        self._rate = rate

    @property
    def tune(self) -> list[Note]:
        return self._tune

    @rate.setter
    def tune(self, tune: list[Note]):
        self._tune = tune

    def play(self) -> None:
        start: int = self._tune[0].tone
        interval: float = 60 / self._rate    # 60 bpm = 1 per sec
        with pwmio.PWMOut(board.GP21, duty_cycle=2 ** 15, frequency=start, variable_frequency=True) as tone:
            for j in range(len(self._tune)):
                if self._tune[j].tone != 0:
                    tone.frequency = self._tune[j].tone
                    tone.duty_cycle = 2 ** 15
                else:
                    tone.duty_cycle = 0
                sleep(interval * (self._tune[j].duration / 4))


class Sequence:
    """ A sequence of frequencies """
    def __init__(self, start: int = 200, interval: float = 1.0, increments: list[int] = [2], end: int = 1000) -> None:
        self._start: int = start
        self._interval: float = interval
        self._increments: list[int] = increments
        self._end: int = end

    @property
    def start(self) -> int:
        return self._start

    @start.setter
    def start(self, start: int):
        self._start = start

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, interval: float):
        self._interval = interval

    @property
    def increments(self) -> list[int]:
        return self._increments

    @increments.setter
    def increments(self, increments: list[int]):
        self._increments = increments

    @property
    def end(self) -> int:
        return self._end

    @end.setter
    def end(self, end: int):
        self._end = end


class Sound:
    """ A sequence of frequencies """
    def __init__(self, interval: float = .1, sequencies: list[Sequence] = []) -> None:
        self._interval: float = interval
        self._sequencies: list[Sequence] = sequencies

    def play(self) -> None:
        for seqn in self._sequencies:
            freq = seqn.start
            with pwmio.PWMOut(board.GP21, duty_cycle=2 ** 15, frequency=freq, variable_frequency=True) as tone:
                while freq != seqn.end:
                    tone.frequency = freq
                    freq += seqn.increments[0]
                    sleep(seqn.interval)


RISING = Sound(interval=0.2, sequencies=[Sequence()])

HI_LO = Tune(rate=140, tune=[Note(C4), Note(C1)])    # Long press error
INPUT = Tune(rate=160, tune=[Note(C5)])              # Button press
FEEDBACK = Tune(rate=160, tune=[Note(G4), Note(0)])  # Confirms input
LO_HI = Tune(rate=120, tune=[Note(C3), Note(C5)])
REMINDER = Tune(rate=120, tune=[Note(F5), Note(0), Note(F5), Note(0), Note(F5), Note(0)])

INPUT_PROMPT = Tune(rate=140, tune=[Note(C3), Note(C5)])
START_UP = Sound(interval=0.2, sequencies=[Sequence(start=300, interval=.1, increments=[10], end=400)])
REBOOT = Sound(interval=0.2, sequencies=[Sequence(start=400, interval=.1, increments=[-10], end=300)])
