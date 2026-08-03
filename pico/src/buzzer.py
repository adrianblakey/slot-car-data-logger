# Copyright @ 2026 Adrian Blakey. All rights reserved
# buzzer.py — the push-pull PWM piezo beeper on GP20/GP21.
#
# The primary substitute for the missing display: every user-visible event
# (Wi-Fi/BLE status, capture start/stop, lap mark, flash warnings, fatal
# error, factory-reset countdown) has a short named tone pattern.
#
# Adapted from the early prototype's buzzer.py, which proved this exact
# push-pull wiring on this exact board (GP20/21 = PWM slice 2 channels A/B;
# inverting channel B roughly doubles the piezo's output by driving both
# leads out of phase). Two fixes vs the prototype:
#   1. playsong() used blocking utime.sleep() — on a board whose whole app
#      runs under asyncio, that would freeze buttons, Wi-Fi and BLE for the
#      duration of every beep. Patterns now run as asyncio.sleep_ms()-paced
#      background tasks (play() is fire-and-forget).
#   2. The prototype played a demo song as an import-time side effect. This
#      module does nothing until main.py constructs a Beeper and calls a
#      named pattern method.

from machine import Pin, PWM, mem32
import asyncio

_TONES = {
    "A4": 440, "AS4": 466, "B4": 494,
    "C5": 523, "CS5": 554, "D5": 587, "DS5": 622, "E5": 659, "F5": 698,
    "FS5": 740, "G5": 784, "GS5": 831, "A5": 880, "AS5": 932, "B5": 988,
    "C6": 1047, "CS6": 1109, "D6": 1175, "DS6": 1245, "E6": 1319, "F6": 1397,
    "FS6": 1480, "G6": 1568, "GS6": 1661, "A6": 1760, "AS6": 1865, "B6": 1976,
    "C7": 2093, "CS7": 2217, "D7": 2349,
    "C4": 262,
}

_PIN_A = 20
_PIN_B = 21

# RP2040 datasheet section 4.5.2: PWM slice n's CSR is at 0x40050000 + 0x14*n.
# GP20/21 map to slice 2, channels A/B. The +0x2000 offset is the RP2040
# "atomic SET" alias (base=normal, +0x1000=XOR, +0x2000=SET, +0x3000=CLR):
# writing there OR's the given bits into the register instead of overwriting
# it, so this sets INVB (bit 3) without disturbing the EN bit the PWM driver
# already set.
_PWM2_CSR_SET = 0x40050000 + 0x14 * 2 + 0x2000
_INVB = 1 << 3

_QUIET_FREQ = 10   # "silence" — 0 Hz freq() is rejected on some ports


class Beeper:
    def __init__(self):
        self._a = PWM(Pin(_PIN_A), duty_u16=32768, freq=1000)
        self._b = PWM(Pin(_PIN_B), duty_u16=32768)
        mem32[_PWM2_CSR_SET] = _INVB   # push-pull: drive B out of phase with A
        self._busy = False

    def _tone(self, name):
        self._a.freq(_TONES[name] if name else _QUIET_FREQ)

    async def _play(self, notes):
        if self._busy:
            return   # a pattern is already sounding — drop this one
        self._busy = True
        try:
            for name, ms in notes:
                self._tone(name)
                await asyncio.sleep_ms(ms)
        finally:
            self._tone(None)
            self._busy = False

    def play(self, notes):
        """Fire-and-forget: schedule a (note_name_or_None, ms) sequence."""
        asyncio.create_task(self._play(notes))

    # ── named event patterns ────────────────────────────────────────────────
    def boot_ready(self):     self.play([("E5", 90), ("G5", 90), ("C6", 140)])
    def wifi_connected(self): self.play([("C6", 80), ("E6", 120)])
    def wifi_failed(self):    self.play([("C5", 150), (None, 60), ("C5", 150)])
    def ble_connected(self):  self.play([("G5", 80), ("C6", 80)])
    def capture_start(self):  self.play([("C6", 70)])
    def capture_stop(self):   self.play([("G5", 70)])
    def lap_mark(self):       self.play([("C7", 40)])
    def flash_low(self):      self.play([("A4", 90), (None, 60), ("A4", 90)])
    def flash_full(self):     self.play([("A4", 150), ("A4", 150), ("A4", 150)])
    def fatal_error(self):    self.play([("C4", 200), (None, 80), ("C4", 200),
                                          (None, 80), ("C4", 200)])
    def reset_tick(self):     self.play([("A5", 30)])
    def reset_confirmed(self): self.play([("C6", 100), ("G5", 100), ("C5", 200)])
