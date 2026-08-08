# Copyright @ 2026 Adrian Blakey. All rights reserved
# tests/mocks.py — MicroPython stubs for host (CPython) testing.
#
# Import this FIRST in any test file that (directly or transitively) touches
# a hardware-facing module. It patches sys.modules so MicroPython-only
# imports resolve to fakes. Adapted from the Pico 2 W reference's mocks.py,
# trimmed of SD/uctypes/rp2/sdcard (this board has none of that) and
# extended with aioble/bluetooth (this board's BLE stack).
#
# error_buffer.py, logconfig.py, log_record.py and flash_writer.py have no
# hardware imports at all and don't need this file — see their test files.
# It exists for adc_device.py/ble_server.py/webserver.py/main.py, none of
# which are host-tested directly (genuinely hardware/network-bound), but a
# future test that imports one of them transitively will need these stubs.

import sys
import types
import time

# ── time (MicroPython tick functions) ──────────────────────────────────────
if not hasattr(time, 'ticks_us'):
    _t0 = time.time()

    def _ticks_us():
        return int((time.time() - _t0) * 1_000_000) & 0x3FFFFFFF

    def _ticks_diff(a, b):
        return a - b

    def _ticks_add(a, b):
        return (a + b) & 0x3FFFFFFF

    time.ticks_us = _ticks_us
    time.ticks_ms = lambda: _ticks_us() // 1000
    time.ticks_diff = _ticks_diff
    time.ticks_add = _ticks_add
    time.sleep_ms = lambda ms: None
    time.sleep_us = lambda us: None

# ── machine ─────────────────────────────────────────────────────────────────
class _Pin:
    OUT = 1
    IN = 0
    PULL_UP = 2
    PULL_DOWN = 3

    def __init__(self, *a, **kw):
        pass

    def value(self, v=None):
        return 0

    def on(self):
        pass

    def off(self):
        pass

    def toggle(self):
        pass

    def __call__(self, v=None):
        return 0


class _ADC:
    def __init__(self, *a, **kw):
        pass

    def read_u16(self):
        return 32768


class _PWM:
    def __init__(self, *a, **kw):
        pass

    def freq(self, *a):
        pass

    def duty_u16(self, *a):
        pass

    def deinit(self):
        pass


class _WDT:
    def __init__(self, **kw):
        pass

    def feed(self):
        pass


_machine = types.ModuleType('machine')
_machine.Pin = _Pin
_machine.ADC = _ADC
_machine.PWM = _PWM
_machine.WDT = _WDT
_machine.mem32 = {}
_machine.reset = lambda: None
_machine.freq = lambda *a: 125_000_000
_machine.unique_id = lambda: b'\x01\x02\x03\x04\x05\x06\x07\x08'
_machine.reset_cause = lambda: 1
_machine.PWRON_RESET = 1
sys.modules['machine'] = _machine

# ── micropython ─────────────────────────────────────────────────────────────
_mp = types.ModuleType('micropython')
_mp.const = lambda x: x
sys.modules['micropython'] = _mp

# ── uasyncio / asyncio ────────────────────────────────────────────────────────
import asyncio as _asyncio
sys.modules['uasyncio'] = _asyncio

# ── _thread ─────────────────────────────────────────────────────────────────
_thread_mod = types.ModuleType('_thread')


class _Lock:
    def acquire(self):
        pass

    def release(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


_thread_mod.allocate_lock = _Lock
_thread_mod.start_new_thread = lambda f, a: None
sys.modules['_thread'] = _thread_mod

# ── network ─────────────────────────────────────────────────────────────────
_network = types.ModuleType('network')
_network.WLAN = lambda *a: types.SimpleNamespace(
    active=lambda *a: None, connect=lambda *a: None, config=lambda *a, **kw: b'\0\0\0\0\0\0',
    isconnected=lambda: False, status=lambda: 0,
    ifconfig=lambda: ('0.0.0.0', '', '', ''))
_network.STA_IF = 0
_network.STAT_GOT_IP = 3
_network.hostname = lambda *a: None
sys.modules['network'] = _network

# ── bluetooth / aioble ────────────────────────────────────────────────────────
_bluetooth = types.ModuleType('bluetooth')
_bluetooth.UUID = lambda x: x
sys.modules['bluetooth'] = _bluetooth

_aioble = types.ModuleType('aioble')
_aioble.Service = lambda *a, **kw: types.SimpleNamespace()
_aioble.Characteristic = lambda *a, **kw: types.SimpleNamespace(
    write=lambda *a, **kw: None, notify=lambda *a, **kw: None,
    written=lambda: None)
_aioble.register_services = lambda *a, **kw: None
_aioble.advertise = lambda *a, **kw: None
sys.modules['aioble'] = _aioble

# ── CONFIG / BOOT stubs ────────────────────────────────────────────────────
_CONFIG = types.ModuleType('CONFIG')
_CONFIG.MODE                 = 'debug'
_CONFIG.LOG_TO_CONSOLE       = True
_CONFIG.LOG_TO_FLASH         = True
_CONFIG.CRASH_PERSIST_JSON   = True
_CONFIG.CRASH_AUTO_REBOOT_MS = 120_000
_CONFIG.REBOOT_BUTTON_PIN    = 16
_CONFIG.SAMPLE_RATE_HZ       = 200
_CONFIG.FLASH_MIN_FREE       = 32 * 1024
_CONFIG.FLASH_LOW_WARN       = 96 * 1024
_CONFIG.FLASH_AUTO_ROTATE    = False
_CONFIG.WIFI_MIN_FREE_BYTES  = 40 * 1024
_CONFIG.BLE_FILE_CHUNK_SIZE  = 180
sys.modules['CONFIG'] = _CONFIG

_BOOT = types.ModuleType('BOOT')
_BOOT.START_WIFI = False
_BOOT.START_BLE  = False
_BOOT.OVERCLOCK  = False
_BOOT.SSID       = ''
_BOOT.PWD        = ''
sys.modules['BOOT'] = _BOOT
