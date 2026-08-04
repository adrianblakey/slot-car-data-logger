# Copyright @ 2026 Adrian Blakey. All rights reserved
# factory_reset.py — headless factory reset (button A held at boot).
#
# The Pico 2 W reference shows a GUI countdown (ResetScreen widget) when its
# Button A is held at boot. This board's Button A is GP16, not the
# reference's GP15 (confirmed on hardware — GP15 is unconnected here; GP16
# is the actual wired button, inherited from the earlier prototype). There
# is no display here, so the countdown is communicated with the piezo
# beeper instead, using blocking time.sleep_ms()
# — this runs from main.py's boot sequence BEFORE asyncio.run() starts, so
# there is nothing else on the board for it to block, and it deliberately
# does not depend on buzzer.Beeper (an asyncio-driven class) for that reason.

import time
import machine
from machine import Pin, PWM

_COUNTDOWN_S = 5
_BEEP_PIN = 20   # same PWM pin buzzer.Beeper uses later; PWM re-init is safe

_DEFAULTS = {
    "BOOT.py": (
        'from micropython import const\n'
        'import logging\n'
        'START_WIFI = True\n'
        'START_BLE = True\n'
        'SSID = const("")\n'
        'PWD = const("")\n'
        'OVERCLOCK = const(False)\n'
        'LOG_LEVEL = logging.DEBUG\n'
        'logging.basicConfig(level=LOG_LEVEL)\n'
    ),
    "CONFIG.py": (
        'MODE = "debug"\n'
        'LOG_TO_CONSOLE = True\n'
        'LOG_TO_FLASH = True\n'
        'CRASH_PERSIST_JSON = True\n'
        'CRASH_AUTO_REBOOT_MS = 120_000\n'
        'REBOOT_BUTTON_PIN = 16\n'
        'SAMPLE_RATE_HZ = 200\n'
        'FLASH_MIN_FREE = 32768\n'
        'FLASH_LOW_WARN = 98304\n'
        'FLASH_AUTO_ROTATE = False\n'
    ),
}


def _beep(freq: int, ms: int) -> None:
    pwm = PWM(Pin(_BEEP_PIN), duty_u16=32768, freq=freq)
    time.sleep_ms(ms)
    pwm.duty_u16(0)
    pwm.deinit()


def _tick() -> None:
    _beep(880, 60)


def _confirmed() -> None:
    for f in (1047, 784, 523):
        _beep(f, 100)
        time.sleep_ms(30)


def check_and_run(pin_num: int = 16, errbuf=None) -> None:
    """
    Synchronous and blocking — call BEFORE asyncio.run() in main.py.

    If the button is not held at boot, returns immediately. If held, beeps
    once per second for _COUNTDOWN_S seconds; releasing at any point cancels.
    If still held when the countdown expires, restores default BOOT.py /
    CONFIG.py and reboots.
    """
    pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
    if pin.value() != 0:
        return   # not held — normal boot

    if errbuf:
        errbuf.record("Factory reset button held at boot — counting down")

    for remaining in range(_COUNTDOWN_S, 0, -1):
        _tick()
        time.sleep_ms(940)   # ~1 s per step including the 60 ms beep
        if pin.value() != 0:
            if errbuf:
                errbuf.record("Factory reset cancelled (button released)")
            return

    if errbuf:
        errbuf.record("Factory reset confirmed — restoring defaults")
    try:
        for fname, content in _DEFAULTS.items():
            with open("/src/" + fname, "w") as f:
                f.write(content)
        _confirmed()
        time.sleep_ms(300)
    except Exception as e:
        if errbuf:
            errbuf.record("Factory reset write failed: {}".format(e))
    machine.reset()
