# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A MicroPython data logger for slot car racing on a **Raspberry Pi Pico W
(RP2040)**, not the Pico 2 W. It samples current/voltage on three ADC
channels and logs to internal flash (no SD card, no display — two buttons,
a piezo beeper, and an abbreviated Wi-Fi/BLE UI). It is a deliberately
downgraded sibling of a separate Pico 2 W reference project
(`aartech-dev/logger`) with an ST7789 display, SD card, and DMA ADC
capture — see [[slot_car_logger_family]] if working across repos. Do not
port the reference's DMA/display/SD-card code here; the departures are
intentional and documented in README.md's "Departures from the Pico 2 W
reference".

Read `README.md` first — it is extensive and covers hardware pinout, the
binary log format, deployment, and (critically) a hardware bring-up log of
six real bugs found and fixed on real silicon, including root causes for
subtle RP2040 PWM and RAM-fragmentation issues. Treat its "What's verified
on hardware" / "What's still unverified" sections as ground truth for what
has actually been tested versus only reasoned about.

## Commands

```bash
make host-test              # run all unit tests on this machine (CPython + mocks), no device needed
python3 pico/tests/run_tests.py   # same, direct
make dist                   # build ./dist from dist_manifest.py (generated, gitignored — don't hand-edit)
make deploy                 # build dist + copy to device over mpremote (DEVICE=/dev/ttyACM0 etc.)
make sync                   # copy only pico/src + pico/tests to device — lighter than deploy, for iteration
make device-test            # sync + run tests on the Pico itself via mpremote
make clean                  # remove src/tests/lib/static/conf from the device
./build.sh                  # Docker UF2 build, frozen mode (default) -> output/firmware.uf2
./build.sh mpy              # Docker UF2 build, base firmware + separate .mpy files
```

To run a single host test: `python3 -m unittest pico.tests.test_flash_writer -v` from repo root won't work directly because `pico/tests/run_tests.py` manually inserts `pico/src` and `pico/tests` onto `sys.path` — either run the whole suite or add the same two directories to `PYTHONPATH` first.

There is no separate lint/typecheck command in this repo.

## Architecture

**Two physical repos of source, kept in sync by hand:** `pico/` is the
edited source tree; `dist/` is a generated mirror built by `make_dist.py`
from `dist_manifest.py` (gitignored — never edit `dist/` directly, it will
be overwritten). `dist_manifest.py` is the single source of truth for
exactly which files ship to the device; there is no automated drift check
against `pico/src/` (the Pico 2 W reference has one, this project doesn't
— keep them in sync by hand when adding/removing a module).

**Two build paths that must be kept in sync:** `dist_manifest.py` (files
copied to the device filesystem via `make deploy`/mpremote) and
`manifest.py` (modules frozen into firmware via `./build.sh`). `BOOT.py`,
`CONFIG.py`, and `main.py` are deliberately excluded from freezing in both
— they must stay filesystem-editable without a reflash.

**Two precompiled `.mpy` files are committed to git** (`pico/src/webserver.mpy`,
`pico/lib/microdot/microdot.mpy`) because live-compiling their `.py` source
on-device needs a contiguous heap allocation that this 264 KB-RAM board
can't reliably provide once Wi-Fi+BLE+ADC are all resident. The `.py`
source stays in the repo for editing; after changing it, regenerate the
`.mpy` with `mpy-cross` (exact invocation and required `mpy-cross` version
are in comments at the top of `dist_manifest.py`) and commit both.

**Runtime shape (`pico/main.py`):** a fixed, order-dependent boot sequence
(sys.path setup → pre-log error buffer → factory-reset check → logging →
exception handlers → Core 1 ADC thread start → Core 0 asyncio tasks), then
one asyncio task per concern: publisher (drains the Core 1 ring buffer,
scales raw ADC counts to physical units, fans out to subscriber queues),
buttons, beeper, flash writer, flash-quota monitor, optional Wi-Fi (which
itself spawns the web server and a link monitor), optional BLE, watchdog.
Core 1 runs a tight, allocation-free polling loop in `adc_device.py` and
talks to Core 0 only through a lock-guarded ring buffer of plain integers
(`array.array`) — never allocate or touch asyncio/logging from Core-1-side
code (see `_core1_exception_handler`'s docstring in `main.py`).

**BLE is a fallback at boot, not a peer of Wi-Fi.** `main.py`'s `_main()`
only starts the BLE task if Wi-Fi is unconfigured or failed to connect —
running Wi-Fi web server + BLE GATT + the ADC pipeline simultaneously was
confirmed on real hardware to sit right at this board's memory ceiling
under an *unfrozen* deploy. Don't change this boot-time policy to "start
both whenever both are configured" without re-verifying against that
constraint on the specific build mode in use: a frozen `./build.sh` build
now measurably has ~40 KB more free RAM at boot (131968 vs ~91808 bytes,
confirmed on hardware — see README "What's verified on hardware"), and
the *dynamic* BLE-triggered path below held up fine under it, but the
boot-time decision itself hasn't been re-tested with a frozen build.

That policy has one deliberate, narrower exception: once BLE is running,
its control characteristic accepts a "start Wi-Fi" command
(`CMD_WIFI_START`, see `main.py`'s `_do_wifi_start_async`) that *does*
keep BLE alive alongside the resulting Wi-Fi connection, gated by a
`gc.mem_free()` check against `CONFIG.WIFI_MIN_FREE_BYTES` rather than
the hardware measurement the boot-time rule is based on. Confirmed
working end-to-end on real hardware, including a 90 s sustained run under
a frozen build with Wi-Fi+BLE+web-server+ADC all live via a `bleak`
central (zero disconnects; one non-fatal, self-recovering notify warning
right after the Wi-Fi-stop command, not chased down further) — but that's
still short next to a real multi-minute logging session, so the
threshold's margin over a longer window remains a judgement call, not a
measured limit (see README "What's still unverified"). Don't conflate the
two policies: the boot-time path still never runs both together.

**BLE has real, hardware-confirmed ceilings below what the BLE spec
alone would suggest.** All found the hard way building `ble_server.py`'s
Files service (see README's "found and fixed on hardware" #11-15 for the
full story each), and worth checking before adding more BLE surface:
advertising payload maxes out around 2 custom 128-bit service UUIDs, not
whatever the 31-byte spec limit implies once the device name is added;
this specific MicroPython BLE build silently drops characteristics past
some total-GATT-attribute-count ceiling (a 3rd characteristic on Files
just didn't register — no error, `register_services()` "succeeded");
GATT attribute values are capped at 512 bytes per the BLE spec itself,
which anything JSON-based hits fast; real BLE centrals cannot be assumed
to negotiate a usable MTU even after the device explicitly asks (writes
over ~20 bytes are the risky zone, and fail by silently truncating, not
erroring); and reading a characteristic back-to-back with no delay after
triggering a device-side update can produce a torn read of the buffer,
not just a stale one — pace producer/consumer characteristic pairs by at
least 100ms.

**Storage format:** each sample is an 8-byte packed binary record
(`struct '<Hhhh'`: dt_ms, current centi-amps, track/supply centivolts) in
`pico/src/log_record.py`, not CSV — flash space is scarce with no SD card.
A lap marker is a record with `current_cA == -32768` (sentinel, not a
separate record type). `tools/decode_log.py` converts a pulled-off session
file to CSV/pandas on a host machine; the web UI also exposes an on-device
CSV conversion endpoint.

**Pin numbers are board-specific and easy to get wrong by analogy with the
Pico 2 W reference.** Buttons are GP16 (A) / GP22 (B); GP15/GP17 look like
the "obvious" choice by analogy to the reference board but are unconnected
on this one — this was an actual bug, fixed after hardware testing (see
README's hardware bring-up log). Don't change these without re-confirming
against real hardware.

**Tests (`pico/tests/`)** run on host CPython against `pico/tests/mocks.py`,
which stubs `machine`, `network`, `aioble`, `bluetooth`, `_thread`,
`CONFIG`, `BOOT`. Modules with no hardware imports at all
(`log_record.py`, `flash_writer.py`, `error_buffer.py`) are tested directly
without mocking.
