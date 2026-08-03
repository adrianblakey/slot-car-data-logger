# Copyright @ 2026, Adrian Blakey. All rights reserved
# boot.py — runs before main.py. Sets up /src on sys.path, a pre-log
# ErrorBuffer for anything that happens before logconfig is up, and turns
# the onboard LED on as a "board is alive" signal.
#
# Unlike the Pico 2 W reference's boot.py, Wi-Fi is NOT connected here: that
# reference implementation blocks in a scan/connect loop at this stage
# (duplicating, and racing, main.py's own Wi-Fi task). Wi-Fi and BLE come up
# as ordinary asyncio tasks in main.py instead — connecting is the kind of
# thing that can and should happen concurrently with everything else.

import sys
import machine
from machine import Pin

if "/src" not in sys.path:
    sys.path.insert(0, "/src")

from micropython import const
from error_buffer import ErrorBuffer

_ERR_BUF_SIZE = const(32)
errbuf = ErrorBuffer(_ERR_BUF_SIZE)

try:
    from BOOT import OVERCLOCK
    if OVERCLOCK:
        machine.freq(200_000_000)
        errbuf.record("Overclocking to 200 MHz")
except Exception as e:
    errbuf.record("BOOT.py import failed: {}".format(e))

Pin("LED", Pin.OUT).on()

if machine.reset_cause() != machine.PWRON_RESET:
    errbuf.record("Non-power-on reset, cause={}".format(machine.reset_cause()))
