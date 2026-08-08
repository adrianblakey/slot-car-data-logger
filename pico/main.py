# Copyright @ 2026 Adrian Blakey. All rights reserved.
#
# main.py — Pico W (RP2040) Slot Car Logger
#
# Downgraded sibling of the Pico 2 W reference: no display, no SD card, two
# buttons + a beeper, Wi-Fi + BLE standing in for the missing screen. See
# pico/src/adc_device.py and pico/src/log_record.py for the two biggest
# architectural departures (polled ADC instead of chained DMA; an 8-byte
# binary record instead of CSV) and why.
#
# Boot sequence (stages must not be reordered):
#   1. sys.path guard - /src importable from anywhere.
#   2. Grab the pre-log ErrorBuffer from boot.py.
#   3. Factory-reset check (Button A held at boot) - blocking, headless.
#   4. Logging: timestamped syslog file, flush errbuf.
#   5. Exception handlers: asyncio loop handler + Core 1 fault bridge.
#   6. Core 1: polled ADC capture thread.
#   7. Core 0 asyncio tasks: publisher, monitor, buttons, beeper, flash
#      writer, flash quota monitor, Wi-Fi (optional), BLE (optional),
#      web server (optional, needs Wi-Fi), watchdog.

import sys
import gc
import time
import array
import struct
import _thread
import asyncio
from micropython import const

# ── 1. sys.path ────────────────────────────────────────────────────────────
if "/src" not in sys.path:
    sys.path.insert(0, "/src")

# ── 2. Pre-log ErrorBuffer ────────────────────────────────────────────────
try:
    from boot import errbuf
except Exception as _boot_err:
    from error_buffer import ErrorBuffer
    errbuf = ErrorBuffer(32)
    errbuf.record("boot.py import failed: {}".format(_boot_err))

from machine import Pin, WDT
import logconfig
import fatal_handler
from factory_reset import check_and_run as _factory_reset_check
from adc_device import ADCDevice
import adc_device as _adc
from buzzer import Beeper
from primitives import Pushbutton, RingbufQueue
import flash_writer as fw
from flash_writer import FlashWriter

try:
    from CONFIG import MODE, SAMPLE_RATE_HZ, CRASH_AUTO_REBOOT_MS, WIFI_MIN_FREE_BYTES
except Exception:
    MODE = "debug"
    SAMPLE_RATE_HZ = 200
    CRASH_AUTO_REBOOT_MS = 120_000
    WIFI_MIN_FREE_BYTES = 40 * 1024

try:
    from BOOT import START_WIFI, START_BLE
except Exception:
    START_WIFI = False
    START_BLE = False

from session_profile import PROFILE, LANE_COLORS, lane_color

log = None   # assigned in _setup_logging()

# ── Inter-core shared state ────────────────────────────────────────────────
_stop_flag       = [False]
_core1_lock      = _thread.allocate_lock()
_core1_fault_msg = [""]

# Zero-allocation ring: Core 1 writes only machine integers. Layout: 4 int32
# per slot = (t_us, raw_adc0, raw_adc1, raw_adc2). Sized generously for a
# 200 Hz default rate (256 slots ~= 1.28 s of buffering) while staying a
# power of 2, as adc_device.py requires.
_RING_SLOTS = const(256)
_ring      = array.array('i', (0 for _ in range(_RING_SLOTS * 4)))
_ring_head = array.array('i', [0])    # written by Core 1 only
_ring_tail = array.array('i', [0])    # written by Core 0 only

# Direct fan-out, same shape as the reference: publisher packs one wire
# tuple and put_nowait's it to every subscriber (flash writer, /ws clients).
# Format must match webserver.LIVE_FMT.
_LIVE_FMT = '<ifff'   # t_us(i32), current_A, track_V, supply_V
_subscribers: list = []

_recording       = [False]   # Button A / BLE / web toggle
_marker_pending  = [False]   # Button B / BLE / web one-shot
_beeper: Beeper = None       # constructed in _start_core0_singletons()
_writer: FlashWriter = None  # constructed in _start_core0_singletons()
_wifi = None                 # WiFiConnection, set if START_WIFI or BLE-started
_ble  = None                 # BLEServer, set if START_BLE

# Handles for the two tasks _wifi_task() spawns on a successful connect —
# kept so a later BLE "stop Wi-Fi" command can cancel them. See
# _do_wifi_stop_async().
_webserver_task_handle = None
_wifi_monitor_task_handle = None

from asyncio import ThreadSafeFlag as _TSF
_core1_fault_ts: _TSF = _TSF()


# ══════════════════════════════════════════════════════════════════════════
# Stage 3 — Factory reset
# ══════════════════════════════════════════════════════════════════════════
def _check_factory_reset() -> None:
    _factory_reset_check(pin_num=16, errbuf=errbuf)


# ══════════════════════════════════════════════════════════════════════════
# Stage 4 — Logging
# ══════════════════════════════════════════════════════════════════════════
def _setup_logging() -> None:
    global log
    log = logconfig.configure("main")
    for entry in errbuf.get_all():
        log.info("[pre-log] %s", entry)
    log.info("=== Slot Car Logger (Pico W) starting. mode=%s gc.free=%d ===",
              MODE, gc.mem_free())


# ══════════════════════════════════════════════════════════════════════════
# Stage 5 — Exception handlers
# ══════════════════════════════════════════════════════════════════════════

def _asyncio_exception_handler(loop, context: dict) -> None:
    exc = context.get("exception")
    msg = context.get("message", "unknown")
    try:
        log.error("Core 0 task exception: %s  msg=%s",
                  type(exc).__name__ if exc else "?", msg)
    except Exception:
        pass
    if exc is not None:
        asyncio.create_task(fatal_handler.handle_fatal(exc, log, source="Core0"))


def _core1_exception_handler(exc_type, exc_value) -> None:
    """Called from inside ADCDevice.run()'s except block, ON CORE 1. Must not
    allocate or touch asyncio/logging — print() and a ThreadSafeFlag only."""
    msg = "{}: {}".format(exc_type.__name__ if exc_type else "?", exc_value)
    print("Core1: fault:", msg)
    _core1_fault_msg[0] = msg
    with _core1_lock:
        _stop_flag[0] = True
    _core1_fault_ts.set()


async def _monitor_core1_task() -> None:
    while True:
        await _core1_fault_ts.wait()
        msg = _core1_fault_msg[0]
        log.critical("Core 1 fault received: %s", msg)
        await fatal_handler.handle_fatal(RuntimeError("Core1 fault: " + msg),
                                          log, source="Core1")
        _core1_fault_ts.clear()


# ══════════════════════════════════════════════════════════════════════════
# Stage 6 — Core 1: ADC capture thread
# ══════════════════════════════════════════════════════════════════════════

_worker = None   # module-level reference keeps the worker alive for the thread


def _start_core1() -> None:
    global _worker
    ADCDevice.fault_handler = _core1_exception_handler
    _worker = ADCDevice(
        ring=_ring, ring_head=_ring_head, ring_tail=_ring_tail,
        ring_slots=_RING_SLOTS, lock=_core1_lock, stop_flag=_stop_flag,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )
    log.info("Starting Core 1 ADC capture thread")
    _thread.start_new_thread(_worker.run, ())


# ══════════════════════════════════════════════════════════════════════════
# Stage 7 — Core 0 asyncio tasks
# ══════════════════════════════════════════════════════════════════════════

# ── 7a. Publisher ───────────────────────────────────────────────────────────

async def _publisher_task() -> None:
    """Drain the Core 1 ring, scale to physical units, fan out to subscribers."""
    log.info("Publisher task started")
    SCALE_I = _adc.VOLT_PER_COUNT / _adc.CURRENT_SENSITIVITY_V_PER_A
    SCALE_V = _adc.VOLT_PER_COUNT * _adc.VOLTAGE_DIVIDER_GAIN
    BATCH = const(20)
    n_published = 0
    last_report = time.ticks_ms()
    ring, head, tail = _ring, _ring_head, _ring_tail
    mask = _RING_SLOTS - 1

    try:
        while True:
            zero = _adc.zero_current_raw
            count = 0
            while count < BATCH:
                t = tail[0]
                h = head[0]
                if t == h:
                    break
                if ((h - t) & 0x3FFFFFFF) > _RING_SLOTS:
                    t = (h - _RING_SLOTS) & 0x3FFFFFFF   # Core 1 lapped us
                i = (t & mask) << 2
                t_us = ring[i]
                current_A = (ring[i + 1] - zero) * SCALE_I
                track_V   = ring[i + 2] * SCALE_V
                supply_V  = ring[i + 3] * SCALE_V

                packed = struct.pack(_LIVE_FMT, t_us, current_A, track_V, supply_V)
                for q in _subscribers:
                    try:
                        q.put_nowait(packed)
                    except Exception:
                        pass   # subscriber overrun - oldest discarded
                tail[0] = (t + 1) & 0x3FFFFFFF
                count += 1
            n_published += count

            if time.ticks_diff(time.ticks_ms(), last_report) >= 5000:
                log.info("Publisher: %d samples total, %d subscribers",
                          n_published, len(_subscribers))
                last_report = time.ticks_ms()
            await asyncio.sleep_ms(5)
    except asyncio.CancelledError:
        log.info("Publisher task cancelled")
        raise


# ── 7b. Buttons + beeper wiring ─────────────────────────────────────────────

def _do_start() -> None:
    if _recording[0]:
        return
    _recording[0] = True
    _beeper.capture_start()
    log.info("Recording ON")


def _do_stop() -> None:
    if not _recording[0]:
        return
    _recording[0] = False
    _beeper.capture_stop()
    log.info("Recording OFF")


def _do_mark() -> None:
    if not _recording[0]:
        return
    _marker_pending[0] = True
    _beeper.lap_mark()
    log.info("Lap marker armed")


def _on_btn_a_short() -> None:
    """Toggle capture on/off — same semantics as the Pico 2 W reference's
    Button A, just with a beep instead of a display icon."""
    if _recording[0]:
        _do_stop()
    else:
        _do_start()


def _on_btn_b_short() -> None:
    _do_mark()


async def _buttons_task() -> None:
    log.info("Button task started")
    # GP16 doubles as the factory-reset pin, checked synchronously before
    # asyncio starts (see _check_factory_reset) — safe to reuse at runtime.
    # Pin numbers match this board's actual wiring (confirmed on hardware
    # by watching raw pin state while pressing each button — GP16 = black/A,
    # GP22 = yellow/B), inherited from the earlier prototype; NOT the Pico 2 W
    # reference's GP15/GP17, which are unconnected on this board.
    btn_a = Pushbutton(Pin(16, Pin.IN, Pin.PULL_UP), suppress=True)
    btn_b = Pushbutton(Pin(22, Pin.IN, Pin.PULL_UP), suppress=True)
    btn_a.release_func(_on_btn_a_short)
    btn_b.release_func(_on_btn_b_short)
    try:
        while True:
            await asyncio.sleep_ms(50)
    except asyncio.CancelledError:
        log.info("Button task cancelled")
        raise


def _do_erase() -> None:
    """Only takes effect if not currently recording — silently deleting a
    driver's in-progress session out from under them is worse than making
    them stop first. Clears both session data and syslog files (the
    currently-open log is left alone — see logconfig.erase_logs) — download
    anything worth keeping first (see the BLE Files service) since this
    doesn't ask twice."""
    if _recording[0]:
        log.warning("Erase refused: capture still running")
        _beeper.command_rejected()
        return
    n_data = fw.erase_all()
    n_logs = logconfig.erase_logs()
    log.info("Erased %d session file(s), %d log file(s) (BLE command)", n_data, n_logs)
    _beeper.erase_done()


def _do_lane_rotate() -> None:
    PROFILE.rotate_lane()
    log.info("Lane rotated to %d (%s)", PROFILE.lane, lane_color(PROFILE.lane))
    _beeper.profile_changed()
    if _ble is not None:
        _ble.refresh_profile()


def _do_lane_set(lane: int) -> None:
    if not (1 <= lane <= len(LANE_COLORS)):
        log.warning("Lane set refused: %d out of range", lane)
        _beeper.command_rejected()
        return
    PROFILE.update(lane=lane)
    log.info("Lane set to %d (%s)", lane, lane_color(lane))
    _beeper.profile_changed()
    if _ble is not None:
        _ble.refresh_profile()


def _do_race_toggle() -> None:
    PROFILE.toggle_race()
    log.info("Race type set to %s", PROFILE.race)
    _beeper.profile_changed()
    if _ble is not None:
        _ble.refresh_profile()


async def _do_wifi_start_async() -> None:
    """BLE-triggered Wi-Fi start. Deliberately keeps BLE running afterwards
    (unlike the boot-time path in _main(), which treats BLE as a strict
    fallback) — the free-heap check below is the safety net for that. See
    CONFIG.WIFI_MIN_FREE_BYTES."""
    if _wifi is not None and _wifi.connected():
        log.info("Wi-Fi start requested but already connected")
        return
    gc.collect()
    free = gc.mem_free()
    if free < WIFI_MIN_FREE_BYTES:
        log.warning("Wi-Fi start refused: %d bytes free, need %d", free, WIFI_MIN_FREE_BYTES)
        _beeper.command_rejected()
        return
    await _wifi_task()


async def _do_wifi_stop_async() -> None:
    global _webserver_task_handle, _wifi_monitor_task_handle
    if _wifi is None or not _wifi.connected():
        log.info("Wi-Fi stop requested but not connected")
        return
    if _webserver_task_handle is not None:
        _webserver_task_handle.cancel()
        _webserver_task_handle = None
    if _wifi_monitor_task_handle is not None:
        _wifi_monitor_task_handle.cancel()
        _wifi_monitor_task_handle = None
    _wifi.disconnect()
    _beeper.wifi_stopped()
    log.info("Wi-Fi stopped (BLE command)")


def _ble_control_fn(cmd: int, data: bytes = b'') -> None:
    from ble_server import (CMD_START, CMD_STOP, CMD_MARK, CMD_ERASE,
                             CMD_WIFI_START, CMD_WIFI_STOP,
                             CMD_LANE_ROTATE, CMD_LANE_SET, CMD_RACE_TOGGLE)
    if cmd == CMD_START:
        _do_start()
    elif cmd == CMD_STOP:
        _do_stop()
    elif cmd == CMD_MARK:
        _do_mark()
    elif cmd == CMD_ERASE:
        _do_erase()
    elif cmd == CMD_WIFI_START:
        asyncio.create_task(_do_wifi_start_async())
    elif cmd == CMD_WIFI_STOP:
        asyncio.create_task(_do_wifi_stop_async())
    elif cmd == CMD_LANE_ROTATE:
        _do_lane_rotate()
    elif cmd == CMD_LANE_SET:
        if len(data) >= 2:
            _do_lane_set(data[1])
        else:
            log.warning("Lane set command missing its payload byte")
    elif cmd == CMD_RACE_TOGGLE:
        _do_race_toggle()
    else:
        log.warning("Unknown BLE control command: %d", cmd)


def _status_dict() -> dict:
    return {
        'recording': _recording[0],
        'flash_free_pct': _flash_free_pct(),
        'record_count': _writer.record_count() if _writer else 0,
        'wifi_up': _wifi.connected() if _wifi else False,
    }


def _flash_free_pct() -> int:
    import os
    try:
        st = os.statvfs('/')
        total, free = st[2], st[3]
        return int(free * 100 / total) if total else 0
    except Exception:
        return 0


# ── 7c. Flash writer ─────────────────────────────────────────────────────────

async def _flash_writer_task() -> None:
    """Mirrors the reference's _sd_writer_task, minus the SD card: opens/
    closes one binary session file per _recording[0] on/off cycle, and
    injects the pending Button-B marker into the SAME record stream so
    dt_ms stays a true "since previous record" delta (see log_record.py)."""
    global _writer
    log.info("Flash writer task started")
    queue: RingbufQueue = RingbufQueue(200)
    _subscribers.append(queue)
    _writer = FlashWriter(sample_rate_hz=SAMPLE_RATE_HZ)
    was_recording = False

    try:
        while True:
            packed = await queue.get()
            t_us, current_A, track_V, supply_V = struct.unpack(_LIVE_FMT, packed)

            if _recording[0]:
                if not was_recording:
                    try:
                        fname = _writer.start()
                        was_recording = True
                        log.info("Session started: %s", fname)
                    except fw.FlashQuotaError as e:
                        log.error("Cannot start session: %s", e)
                        _recording[0] = False
                        _beeper.flash_full()
                        continue

                if _marker_pending[0]:
                    _marker_pending[0] = False
                    _writer.write_marker(t_us, track_V, supply_V)
                _writer.write_sample(t_us, current_A, track_V, supply_V)

                if _writer.record_count() % 100 == 0:
                    _writer.flush()
            else:
                if was_recording:
                    n = _writer.record_count()
                    _writer.close()
                    was_recording = False
                    log.info("Session closed (%d records)", n)

    except asyncio.CancelledError:
        if was_recording:
            _writer.close()
        try:
            _subscribers.remove(queue)
        except ValueError:
            pass
        log.info("Flash writer task cancelled")
        raise


async def _flash_quota_task() -> None:
    """Stop recording when flash drops below CONFIG.FLASH_MIN_FREE; warn at
    CONFIG.FLASH_LOW_WARN. Polled rather than checked per-sample — cheap and
    frequent enough (2 s) given the small floors involved."""
    warned = False
    while True:
        await asyncio.sleep(2)
        state = FlashWriter.quota_state()
        if state == "full":
            if _recording[0]:
                log.error("Flash below floor — stopping recording")
                _do_stop()
                _beeper.flash_full()
        elif state == "low":
            if not warned:
                _beeper.flash_low()
                warned = True
        else:
            warned = False


# ── 7d. Wi-Fi + web server ───────────────────────────────────────────────────

async def _wifi_task() -> bool:
    """
    Connect to Wi-Fi and, if successful, start the web server + link
    monitor as independent background tasks. Returns True/False so callers
    can decide what to do next — _main() decides whether to also start BLE
    at boot (see its comment for why that's conditional, not "and" —
    confirmed on hardware); _do_wifi_start_async() calls this directly for
    a BLE-triggered start, after its own free-heap check.

    The two spawned tasks' handles are stashed in module globals so a later
    BLE "stop Wi-Fi" command can cancel them (_do_wifi_stop_async()) — this
    function itself doesn't run again until the next start, so it can't
    hold onto them locally.
    """
    global _wifi, _webserver_task_handle, _wifi_monitor_task_handle
    from wifi_connection import WiFiConnection
    log.info("Wi-Fi task starting")
    _wifi = WiFiConnection()
    try:
        if await _wifi.connect():
            _beeper.wifi_connected()
            log.info("Wi-Fi connected: %s", _wifi.ip())
            _webserver_task_handle = asyncio.create_task(_webserver_task())
            _wifi_monitor_task_handle = asyncio.create_task(_wifi.monitor(interval_s=10))
            return True
        _beeper.wifi_failed()
        log.info("No known Wi-Fi network found")
        return False
    except asyncio.CancelledError:
        log.info("Wi-Fi task cancelled")
        raise
    except Exception as exc:
        log.error("Wi-Fi task failed: %s", exc)
        return False


async def _webserver_task() -> None:
    # gc.collect() BEFORE this import, not after: microdot.py is one large
    # (~2000 line) module, and parsing/compiling it needs a big contiguous
    # allocation. Confirmed on hardware (264 KB RAM RP2040): importing
    # ble_server then webserver back-to-back with no collect() in between
    # raised MemoryError even though enough total free heap existed — the
    # prior import's garbage had fragmented it. A collect() right before the
    # big import compacts the heap so the allocation has room.
    gc.collect()
    from webserver import app, configure as configure_webserver
    configure_webserver(_status_dict, _do_start, _do_stop, _do_mark, _subscribers)
    log.info("Web server starting on :80")
    try:
        await app.start_server(host='0.0.0.0', port=80, debug=(MODE != "production"))
    except asyncio.CancelledError:
        log.info("Web server task cancelled")
        raise
    except Exception as exc:
        log.error("Web server task failed: %s", exc)
        raise


# ── 7e. BLE ───────────────────────────────────────────────────────────────────

async def _ble_task() -> None:
    global _ble
    gc.collect()   # see _webserver_task's comment — same fragmentation risk
    from ble_server import BLEServer
    log.info("BLE task starting")
    try:
        _ble = BLEServer()
        _ble.configure(_status_dict, _ble_control_fn,
                        ip_getter=lambda: _wifi.ip() if _wifi else None,
                        on_connect=_beeper.ble_connected)
        await _ble.run()
    except asyncio.CancelledError:
        log.info("BLE task cancelled")
        raise
    except Exception as exc:
        log.error("BLE task failed: %s", exc)
        raise


# ── 7f. Watchdog ──────────────────────────────────────────────────────────────

async def _wdt_feed_task(wdt: WDT) -> None:
    try:
        while True:
            wdt.feed()
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        log.info("WDT feed task cancelled")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Top-level async entry point
# ══════════════════════════════════════════════════════════════════════════

async def _main() -> None:
    global _beeper

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_asyncio_exception_handler)

    _beeper = Beeper()
    fatal_handler.configure(_beeper)

    wdt = WDT(timeout=8000) if MODE == "production" else None

    tasks = [
        asyncio.create_task(_publisher_task()),
        asyncio.create_task(_monitor_core1_task()),
    ]
    if wdt is not None:
        tasks.append(asyncio.create_task(_wdt_feed_task(wdt)))
    else:
        log.info("WDT disabled (MODE=debug) - Ctrl-C can stop the app")

    await asyncio.sleep_ms(10)   # let the publisher start draining first

    tasks.append(asyncio.create_task(_buttons_task()))
    tasks.append(asyncio.create_task(_flash_writer_task()))
    tasks.append(asyncio.create_task(_flash_quota_task()))

    # BLE is a FALLBACK at boot, not started alongside a working Wi-Fi web
    # UI. Confirmed on hardware (264 KB RAM RP2040, non-frozen filesystem
    # deploy): Wi-Fi web server + BLE GATT + the ADC pipeline all live at
    # once sits right at this board's capacity — sometimes raising
    # MemoryError even with the heaviest modules (microdot.py, webserver.py)
    # precompiled to .mpy. A frozen firmware build (./build.sh) should have
    # more headroom (see README "Flash budget" / "What's still unverified"),
    # but that hasn't been measured. Until it has, prefer the strictly
    # richer Wi-Fi web UI when it's available and only fall back to BLE
    # when Wi-Fi isn't configured or fails to connect — matching the
    # earlier prototype's own README note that most tracks have no Wi-Fi.
    #
    # This is boot-time policy only. Once BLE is running (i.e. we land in
    # this branch), it now also accepts a "start Wi-Fi" command
    # (CMD_WIFI_START — see _do_wifi_start_async()) that deliberately DOES
    # keep BLE alive alongside the resulting Wi-Fi web UI, rather than
    # stopping BLE the way this boot path would. That's a narrower,
    # opt-in exception to the rule above, gated by a free-heap check
    # (CONFIG.WIFI_MIN_FREE_BYTES) instead of hardware measurement, since a
    # driver explicitly asking to bring Wi-Fi up over BLE presumably still
    # wants BLE control afterwards (e.g. to stop Wi-Fi again).
    wifi_up = False
    if START_WIFI:
        wifi_up = await _wifi_task()
    if START_BLE and not wifi_up:
        tasks.append(asyncio.create_task(_ble_task()))
    elif START_BLE and wifi_up:
        log.info("Wi-Fi web UI is up - BLE not started (see main.py comment)")

    _beeper.boot_ready()
    log.info("All tasks launched. gc.free=%d", gc.mem_free())

    try:
        await asyncio.gather(*tasks)
    except Exception as exc:
        log.critical("Top-level gather exception: %s", exc)
        await fatal_handler.handle_fatal(exc, log, source="gather")


# ══════════════════════════════════════════════════════════════════════════
# Synchronous boot (stages 3-6, before asyncio.run)
# ══════════════════════════════════════════════════════════════════════════

def _boot() -> None:
    _check_factory_reset()   # stage 3
    _setup_logging()         # stage 4
    _start_core1()           # stage 6
    time.sleep_ms(50)        # let Core 1 finish calibration before Core 0 reads it


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        _boot()
        asyncio.run(_main())
    except KeyboardInterrupt:
        with _core1_lock:
            _stop_flag[0] = True
        if log:
            log.info("Keyboard interrupt - shutting down")
        else:
            print("Keyboard interrupt - shutting down")
    except Exception as exc:
        import io
        buf = io.StringIO()
        sys.print_exception(exc, buf)
        trace = buf.getvalue()
        print("FATAL boot error:\n", trace)
        if log:
            log.critical("Boot error: %s", trace)
        try:
            from crash_report import write_report
            write_report(type(exc), exc, trace)
        except Exception:
            pass
        raise
    finally:
        with _core1_lock:
            _stop_flag[0] = True
        asyncio.new_event_loop()
