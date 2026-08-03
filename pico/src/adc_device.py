# Copyright @ 2026 Adrian Blakey. All rights reserved
# adc_device.py — standalone Core 1 ADC capture worker (RP2040, Pico W).
#
# Downgrade vs the Pico 2 W reference (adc_worker.py): that file hand-tunes
# RP2350 uctypes register maps for chained dual-DMA capture at ~7.5 kHz
# oversampled/decimated to 1 kHz — a design validated only on real RP2350
# hardware, whose register layout (base addresses, DREQ numbers, the RP2350
# ISO pad bit) does not carry over to RP2040. There is no bench here to
# validate a from-scratch RP2040 DMA port, and a "downgraded" no-display,
# no-SD device doesn't need 7.5 kHz oversampling. Instead this worker polls
# `machine.ADC.read_u16()` directly — the same primitive the earlier
# prototype's device.py already used successfully on this exact board —
# paced to CONFIG.SAMPLE_RATE_HZ (default 200 Hz) in a tight Core 1 loop.
#
# ── Core 1 design rules (same as the reference, still apply) ──────────────────
#   1. ZERO heap allocation inside the run loop after init. The ADC objects
#      are constructed in __init__, which MUST run on Core 0 — allocation on
#      Core 1 while Core 0's GC is also running is not reentrant and can
#      silently wedge Core 1.
#   2. No logging-module calls, ever, in the loop. print() only in one-time
#      init / shutdown / exception paths.
#   3. Data leaves Core 1 through a pre-allocated integer ring buffer built
#      on Core 0. Core 1 writes head; Core 0 (publisher) writes tail; a
#      _thread lock (also allocated on Core 0) guards head publication and
#      the stop flag.
#   4. The worker object MUST be constructed on Core 0. Only the bound
#      method worker.run is handed to _thread.start_new_thread.

import time
import array
from machine import ADC, Pin

MIN_RATE, MAX_RATE = 10, 2000     # sane bounds for a polled (no-DMA) capture

ADC_PIN_26 = 26   # ADC0 - current, LEM CASR 50-NP, +-0.025 V/A
ADC_PIN_27 = 27   # ADC1 - track voltage divider
ADC_PIN_28 = 28   # ADC2 - supply voltage divider

# ── Scaling constants (applied on Core 0 by the publisher) ────────────────────
# machine.ADC.read_u16() always returns a 16-bit-scaled value regardless of
# the underlying 12-bit SAR resolution, so these are simpler than the
# reference's raw-12-bit-register maths — same constants the early prototype
# (device.py) proved on this board.
VOLT_PER_COUNT        = 3.3 / 65535     # ADC reference / full u16 range
CURRENT_SENSITIVITY_V_PER_A = 0.025     # LEM CASR 50-NP
VOLTAGE_DIVIDER_GAIN  = 17.966 / 3.3    # divider: 0-18V track/supply -> 0-3.3V

# Zero-current offset in u16 ADC counts. Updated by calibrate_current();
# read by the Core 0 publisher (import adc_device; adc_device.zero_current_raw).
zero_current_raw: int = 32768   # mid-scale until calibrated


class ADCDevice:
    """
    Core 1 ADC capture worker. Construct on Core 0, then:
        _thread.start_new_thread(worker.run, ())
    Stop by setting stop_flag[0] = True under the lock.
    """

    # Set by main.py to escalate Core 1 exceptions: ADCDevice.fault_handler = fn
    fault_handler = None

    def __init__(self, ring, ring_head, ring_tail, ring_slots, lock, stop_flag,
                 sample_rate_hz: int = 200):
        if ring_slots & (ring_slots - 1):
            raise ValueError("ring_slots must be a power of 2")
        if not MIN_RATE <= sample_rate_hz <= MAX_RATE:
            raise ValueError("sample_rate_hz out of range (%d..%d)" % (MIN_RATE, MAX_RATE))

        self._ring  = ring
        self._head  = ring_head
        self._tail  = ring_tail
        self._mask  = ring_slots - 1
        self._lock  = lock
        self._stop  = stop_flag
        self._interval_us = 1_000_000 // sample_rate_hz
        self._running = False

        # ADC objects are constructed HERE, on Core 0 — allocation-free from
        # this point on. Reading them in the Core 1 loop is a machine-level
        # register access, not a Python allocation.
        self._adc0 = ADC(Pin(ADC_PIN_26))
        self._adc1 = ADC(Pin(ADC_PIN_27))
        self._adc2 = ADC(Pin(ADC_PIN_28))

        print("Core1: ADCDevice ready  pins 26/27/28  rate =",
              sample_rate_hz, "Hz  interval =", self._interval_us, "us")

    # ── Hardware init (one-time, prints allowed) ──────────────────────────────

    def calibrate_current(self, samples: int = 32) -> None:
        """Average `samples` ADC0 readings at rest (no current flowing)."""
        global zero_current_raw
        total = 0
        for _ in range(samples):
            total += self._adc0.read_u16()
            time.sleep_ms(1)
        zero_current_raw = total // samples
        print("Core1: zero_current_raw =", zero_current_raw)

    # ── Thread entry and main loop ────────────────────────────────────────────

    def run(self):
        """Thread entry point: _thread.start_new_thread(worker.run, ())."""
        if self._running:
            print("Core1: already running - ignoring run() call")
            return
        self._running = True
        print("Core1: thread started")
        try:
            self.calibrate_current()
            self._loop()
            print("Core1: thread finished cleanly")
        except Exception as e:
            print("Core1: EXCEPTION ", type(e).__name__, " ", e)
            fh = ADCDevice.fault_handler
            if fh is not None:
                try:
                    fh(type(e), e)
                except Exception:
                    pass
        finally:
            self._running = False

    def _loop(self):
        """
        Allocation-free polling loop: read three channels, timestamp, store,
        pace to the target interval. No DMA — the ADC's own conversion time
        (a few microseconds per channel) plus a tight sleep_us gives ample
        margin at the target rates (10-2000 Hz) without missing a beat even
        with Core 0 busy on Wi-Fi/BLE, since a Core 0 GC pause only delays
        THIS iteration's write, never corrupts it (unlike an unpaced DMA
        FIFO, there is no overrun to recover from — read_u16() just runs a
        touch late).
        """
        lock = self._lock
        stop = self._stop
        ring = self._ring
        head = self._head
        mask = self._mask
        interval = self._interval_us
        adc0, adc1, adc2 = self._adc0, self._adc1, self._adc2

        next_due = time.ticks_add(time.ticks_us(), interval)

        while True:
            lock.acquire()
            s = stop[0]
            lock.release()
            if s:
                print("Core1: stop flag set - exiting loop")
                break

            t = time.ticks_us()
            r0 = adc0.read_u16()
            r1 = adc1.read_u16()
            r2 = adc2.read_u16()

            h = head[0]
            i = (h & mask) << 2
            ring[i]     = t
            ring[i + 1] = r0
            ring[i + 2] = r1
            ring[i + 3] = r2

            lock.acquire()
            head[0] = (h + 1) & 0x3FFFFFFF
            lock.release()

            # Pace to the next slot. If we're already late (Core 0 stole a
            # lot of time), skip straight to the next boundary instead of
            # accumulating drift.
            now = time.ticks_us()
            remaining = time.ticks_diff(next_due, now)
            if remaining > 0:
                time.sleep_us(remaining)
                next_due = time.ticks_add(next_due, interval)
            else:
                next_due = time.ticks_add(now, interval)
