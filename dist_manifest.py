# Copyright @ 2026 Adrian Blakey. All rights reserved
# dist_manifest.py — explicit device distribution manifest.
#
# Single source of truth for what ships to the device: every file is
# enumerated (repo path, device path). Nothing is copied that is not listed
# here. Adapted from the Pico 2 W reference's dist_manifest.py, with the
# display/SD-card entries (gui/, drivers/, sdcard.py, rp_devices.py) dropped
# and this board's actual modules substituted.
#
# Maintenance: this simplified make_dist.py only builds ./dist from the list
# below — the reference's two-way import-graph drift check (make_dist.py
# --check, backed by find_unused.py) was not ported; keep this list in sync
# with pico/src/ and pico/lib/ by hand.
#
# Device layout: main.py/boot.py at root; application modules under /src
# (boot.py puts /src on sys.path); libraries under /lib (MicroPython's
# default sys.path already includes /lib); conf and static trees copied
# whole.

ROOT = [
    ("pico/main.py", "main.py"),
    ("pico/boot.py", "boot.py"),
]

SRC = [("pico/src/%s.py" % m, "src/%s.py" % m) for m in (
    # deploy-time editable (never frozen — see manifest.py)
    "BOOT", "CONFIG",
    # core pipeline
    "adc_device", "log_record",
    # storage / logging
    "flash_writer", "session_profile", "error_buffer", "logconfig",
    # crash handling
    "crash_report", "fatal_handler", "factory_reset",
    # user feedback
    "buzzer",
    # connectivity
    "wifi_connection", "ble_server",
)]

# webserver.py ships as precompiled bytecode too, for the same reason as
# microdot.mpy below: confirmed on hardware that its own live compile — on
# top of everything else already resident (Wi-Fi + BLE + the ADC pipeline)
# — is enough by itself to occasionally push a MemoryError. Regenerate with:
#   .venv/bin/mpy-cross pico/src/webserver.py -o pico/src/webserver.mpy
SRC.append(("pico/src/webserver.mpy", "src/webserver.mpy"))

LIB = [("pico/lib/%s" % p, "lib/%s" % p) for p in (
    "logging.py",
    "primitives/__init__.py",
    "primitives/delay_ms.py",
    "primitives/pushbutton.py",
    "primitives/queue.py",
    "primitives/ringbuf_queue.py",
    "microdot/__init__.py",
    "microdot/helpers.py",
    "microdot/websocket.py",
)]

# microdot.py (~2000 lines, one file) ships as precompiled bytecode, not
# source. Confirmed on hardware (264 KB RAM RP2040): parsing/compiling it
# live needs a big contiguous allocation that a fragmented — or just busy,
# with Wi-Fi+BLE+ADC all live — heap can't always satisfy, raising a
# MemoryError that a plain gc.collect() doesn't reliably fix. The .py
# source stays in the repo (pico/lib/microdot/microdot.py) for reference
# and recompilation; only the .mpy ships. Regenerate after editing the
# source with:
#   .venv/bin/pip install mpy-cross==1.27.0.post2   (closest match to the
#     RPI_PICO_W v1.28.0 firmware this was verified against — mismatched
#     .mpy bytecode versions fail to import)
#   .venv/bin/mpy-cross pico/lib/microdot/microdot.py -o pico/lib/microdot/microdot.mpy
LIB.append(("pico/lib/microdot/microdot.mpy", "lib/microdot/microdot.mpy"))

# Whole directory trees, copied recursively (repo dir, device dir).
TREES = [
    ("pico/conf",   "conf"),
    ("pico/static", "static"),
]


def all_files():
    return ROOT + SRC + LIB
