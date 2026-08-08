# Slot Car Logger — Pico W (RP2040)

A MicroPython data logger for slot car racing, running on the original
**Raspberry Pi Pico W (RP2040)**. It sits inline between the controller and
the track, sampling current and voltage on three ADC channels, and logs
sessions to internal flash. There is no display, no SD card, and no nav
buttons — just two buttons, a piezo beeper, and an abbreviated Wi-Fi/BLE UI.

This is a downgraded sibling of the [aartech-dev/logger](https://github.com/aartech-dev/logger)
Pico 2 W (RP2350) project, which has an ST7789 display, a micro-SD card, and
hardware-chained-DMA ADC capture. See "Departures from the Pico 2 W
reference" below for what changed and why.

**Status:** built and host-tested (`make host-test`, 60 tests), then deployed
to and exercised on a real Pico W. See "What's verified on hardware" and
"What's still unverified" below.

---

## Hardware

| Component | Details |
|-----------|---------|
| MCU | Raspberry Pi Pico W — RP2040 dual Cortex-M0+ @ 125 MHz, CYW43439 Wi-Fi + BLE |
| Current sensor | LEM CASR 50-NP — bipolar, 0.025 V/A, GP26 (ADC0) |
| Voltage inputs | Resistive dividers, 0-18 V -> 0-3.3 V, GP27/28 (ADC1/2) |
| Storage | Internal flash only — no SD card |
| User I/O | 2 buttons + piezo beeper — no display |

### GPIO pin map

| GPIO | Signal | Notes |
|------|--------|-------|
| GP16 | Button A (black) | Short press: toggle capture. Held at boot: factory reset. |
| GP22 | Button B (yellow) | Short press: lap marker (only while capturing). |
| GP20 | Beeper (piezo +) | PWM slice 2A |
| GP21 | Beeper (piezo -, inverted) | PWM slice 2B, driven out of phase for volume |
| GP26 | ADC0 — track current | LEM CASR 50-NP, bipolar |
| GP27 | ADC1 — track voltage | Resistive divider |
| GP28 | ADC2 — supply voltage | Resistive divider |

Button and beeper pins match this board's actual physical wiring, carried
over from the earlier prototype (confirmed on hardware — see "What's
verified on hardware"), **not** the unrelated Pico 2 W reference board's
pin choices. GP15/17/18 and the reference's display/SD/nav pins
(GP2/3/4-13) are all unconnected and free on this board.

---

## Departures from the Pico 2 W reference

**ADC capture: plain `machine.ADC` polling on Core 1, not chained DMA.**
`pico/src/adc_device.py` polls `ADC(26/27/28).read_u16()` in a tight,
allocation-free Core 1 loop, paced to `CONFIG.SAMPLE_RATE_HZ` (default
200 Hz). The reference's `adc_worker.py` hand-tunes RP2350 uctypes register
maps for chained dual-DMA capture at ~7.5 kHz — validated only on real
RP2350 hardware, whose register layout doesn't carry over to RP2040, and
which a "downgraded" no-display device doesn't need anyway.

**Storage format: an 8-byte binary record, not CSV.** No SD card means every
byte on internal flash counts. `pico/src/log_record.py` packs each sample as
`struct '<Hhhh'` — `dt_ms` (ms since the previous record), `i_cA` (current,
centi-amps), `vt_cV`/`vs_cV` (voltages, centivolts) — about 3x smaller than
the reference's CSV rows and half the size of its own 16-byte binary wire
format. A lap marker (Button B) is a record with `i_cA == -32768`, the same
"impossible value" sentinel trick the reference uses for CSV marker rows.
`tools/decode_log.py` converts a session file back to CSV/pandas on a host
machine.

**No display — everything is a beep or a web/BLE read.** `pico/src/buzzer.py`
plays short named tone patterns for every event a screen would otherwise
show (Wi-Fi/BLE status, capture start/stop, lap mark, flash warnings, fatal
errors, factory-reset countdown). `pico/src/webserver.py` serves a single
abbreviated page (status, start/stop/mark, session list + download, profile
form — no live graph) and `pico/src/ble_server.py` exposes the same status/
control/profile surface as a GATT service, for a phone that isn't on the
same Wi-Fi.

**No SD card — internal flash only, with a hard quota guard.**
`pico/src/flash_writer.py` stops capture when free flash drops below
`CONFIG.FLASH_MIN_FREE` (there's no bigger medium to fail over to) rather
than the reference's SD-vs-flash fallback logic.

### Flash budget

Measured on real hardware (mpy/unfrozen deploy — see "What's verified"
below): **868 KB** total littlefs filesystem, **~468 KB** free once this
app's own files are copied on (`main.py`/`boot.py`/`src`/`lib`/`conf`/
`static` — about 380 KB unfrozen). A frozen `./build.sh` build moves most
of the app's `.py` files out of the filesystem and into firmware instead —
confirmed the freed-up files are genuinely gone from littlefs (`:src`
shrinks from 13 files to 2 — `BOOT.py`/`CONFIG.py`, the only ones
`manifest.py` doesn't freeze) — but a clean *before/after free-space*
number wasn't captured: the same device had already been through a long
BLE-testing session (accumulated syslog files, a stray `:tests` directory
from unrelated Makefile testing) by the time the frozen build was
flashed, so free-space bytes measured afterward aren't a fair comparison
against the unfrozen figure above. The **868 KB total** stayed identical
frozen vs unfrozen either way (same fixed littlefs partition regardless of
how much code is frozen) — see "What's verified on hardware" for what
*was* cleanly measured (free RAM, not free flash) on this build.

At the default 200 Hz (8 bytes/record = 1.6 KB/s ≈ 96 KB/min) and ~468 KB
free, that's about **5 minutes** of continuous logging on an unfrozen
deploy. Lower `CONFIG.SAMPLE_RATE_HZ` for longer sessions, download and
erase sessions between runs via the web UI, or use a frozen build.

---

## Repository layout

```
slot-car-data-logger/
├── Dockerfile, build.sh, manifest.py   # Docker UF2 build (frozen or mpy mode)
├── Makefile, dist_manifest.py, make_dist.py   # mpremote deploy helpers
├── tools/decode_log.py                 # host: binary session -> CSV/pandas
├── tools/graph_session_csv.bas         # LibreOffice Calc macro: graph a decoded session
├── tools/ble_cli.py                    # host: command-line client for every BLE function
└── pico/
    ├── boot.py             # pre-main: ErrorBuffer, LED, reset_cause
    ├── main.py              # entry point — boot stages + all asyncio tasks
    ├── conf/                # wifi.json(.example), profile.json
    ├── static/               # abbreviated web UI: index.html/css/js
    ├── lib/                  # Peter Hinch primitives, Microdot, logging.py
    ├── src/                  # application source modules
    └── tests/                # host CPython unit tests (mocks.py)
```

### Key source files

| File | Role |
|------|------|
| `src/BOOT.py` | Wi-Fi/BLE start flags, fallback SSID/password — deploy-time editable |
| `src/CONFIG.py` | Mode, sample rate, flash quota floors — deploy-time editable |
| `src/adc_device.py` | Core 1 capture — polled `machine.ADC`, no DMA |
| `src/log_record.py` | 8-byte binary record pack/unpack, lap-marker sentinel, session header |
| `src/flash_writer.py` | Session file lifecycle + flash quota guard |
| `src/session_profile.py` | `PROFILE` singleton (track/race/lane/controller/car), persisted JSON |
| `src/error_buffer.py` | Pre-log circular ring buffer |
| `src/logconfig.py` | `configure()`/`get_logger()`, flash-only syslog |
| `src/crash_report.py` | Append-only crash JSON on flash |
| `src/fatal_handler.py` | Log -> persist -> beeper pattern -> auto-reboot (no CrashScreen) |
| `src/factory_reset.py` | Headless Button-A-held-at-boot reset, beeper countdown |
| `src/buzzer.py` | Async `Beeper` — named event tone patterns |
| `src/wifi_connection.py` | Multi `conf/wifi*.json` search, async connect |
| `src/ble_server.py` | aioble GATT: device info + logger status/control/profile |
| `src/webserver.py` | Microdot abbreviated web UI |
| `dist_manifest.py` | Host — explicit device distribution manifest |
| `make_dist.py` | Host — build `./dist` from the manifest |

---

## Development setup

```bash
pip install mpremote
```

### Flashing MicroPython

Download the **Pico W** firmware (not Pico 2 W) from
`https://micropython.org/download/RPI_PICO_W/` — the W variant is required
for `aioble` and the CYW43 Wi-Fi/BLE driver. Hold BOOTSEL while connecting
USB, copy the `.uf2` onto the drive that appears.

```python
import sys; print(sys.version)   # v1.21 or later — BLE (aioble) needs it
help("modules")                   # aioble/... must be listed
```

### Installing dependencies

```python
import mip
mip.install("github:peterhinch/micropython-async/v3/primitives")
mip.install("github:miguelgrinberg/microdot")
```

`pico/lib/` already vendors the exact files this project uses (Peter
Hinch's `primitives` — `pushbutton`, `ringbuf_queue`, `queue`, `delay_ms` —
and a trimmed Microdot — `microdot.py`, `websocket.py`, `helpers.py`), so
`make deploy` ships them without needing `mip` on the device at all.

### Credentials

```bash
cp pico/conf/wifi.json.example pico/conf/wifi.json
# edit pico/conf/wifi.json with real credentials
```

`wifi_connection.py` searches `conf/` for every `wifi*.json` file (not just
`wifi.json`) and tries each in turn — handy for carrying more than one
trackside AP's credentials on the device at once. `conf/wifi.json` and any
`conf/wifi-*.json` are gitignored; only `wifi.json.example` is committed.

### Deploying to the device

```bash
make dist         # build ./dist from dist_manifest.py
make deploy        # build ./dist and copy it to the device (recommended)
make sync          # copy src/ and tests/ only — lighter weight, for iteration
make clean         # remove src/tests/lib/static/conf from the device
```

`dist_manifest.py` is the single source of truth for what ships. Unlike the
Pico 2 W reference's `make_dist.py --check`, there is no automated
reachability drift-check here — keep the manifest in sync with `pico/src/`
and `pico/lib/` by hand.

### Building a UF2 (Docker)

```bash
./build.sh          # frozen mode (default) -> output/firmware.uf2
./build.sh mpy       # firmware.uf2 + output/*.mpy for dev iteration
```

`manifest.py` freezes the stable application modules into firmware;
`BOOT.py`, `CONFIG.py`, and `main.py` stay on the filesystem so they're
editable without a reflash (same reasoning as the reference).

---

## Testing

Host-side tests run on CPython, no device needed:

```bash
make host-test
# or directly:
python3 pico/tests/run_tests.py
```

`pico/tests/mocks.py` stubs `machine`, `network`, `aioble`, `bluetooth`,
`_thread`, `CONFIG`, `BOOT` for modules that need them. `log_record.py`,
`flash_writer.py`, and `error_buffer.py` have no hardware imports at all and
are tested directly.

| Test file | Covers |
|-----------|--------|
| `test_log_record.py` | Record/header pack-unpack, clipping, lap-marker sentinel |
| `test_flash_writer.py` | Session lifecycle, quota guard, rotation |
| `test_error_buffer.py` | Pre-log ring buffer |
| `test_logconfig.py` | `configure()`/`get_logger()`, flash-only syslog |
| `test_session_profile.py` | Load/save/update, `rotate_lane`/`toggle_race` |

### What's verified on hardware

Deployed (unfrozen, via `make deploy`) to a real Pico W running MicroPython
v1.28.0 (`RPI_PICO_W` build) and exercised over `mpremote`, including a real
home Wi-Fi network:

- Full `main.py` boot sequence completes cleanly and fast (all stages, every
  task launched within ~1 s of reset), both with and without Wi-Fi config
  present — `wifi_connection.py` skips gracefully with no config, connects
  in ~1 s with it.
- Core 1's polled `adc_device.py` sustains the configured rate: consistently
  ~195-200 samples/s at `SAMPLE_RATE_HZ=200` over multi-minute runs. Raw
  `ADC(26/27/28).read_u16()` reads returned plausible values with no sensor
  board attached (near-zero on the floating voltage dividers, mid-scale on
  the bipolar current sensor's bias point).
- **Full web UI round-trip**: `GET /`, `GET /api/status`, `POST /api/start`
  `/stop`/`/mark`, `GET /api/sessions`, raw session download, and the
  on-the-fly CSV conversion endpoint all tested with real `curl` requests
  against the live device and returned correct data. A session created via
  the web API (`start` → `mark` → `stop`) produced a file whose byte size
  matched the binary format's math exactly.
- `flash_writer.py` end-to-end on real littlefs, both via a direct on-device
  script and via the web API: session files open/close/write correctly,
  and `tools/decode_log.py` correctly decodes a real device-written file
  pulled back over HTTP, including a lap marker row.
- `ble_server.py` genuinely advertises (`bluetoothctl scan` from a Linux
  host found `SCLogger-e6614c`) when Wi-Fi isn't up.
- **Full BLE control surface, from a real central** (a `bleak` script over
  the host's own Bluetooth adapter, connecting to the live device): every
  command in the control characteristic's table — start/stop/mark, erase
  (both refused-while-recording and allowed-while-stopped), lane rotate,
  lane set (both a valid and an out-of-range value, the latter correctly
  refused), race toggle, and Wi-Fi start/stop — round-tripped correctly
  against the status and profile characteristics' actual values on
  hardware, not just read back what was written. Wi-Fi start over BLE in
  particular: the free-heap check passed, a real AP connection came up
  (~6 s), and the BLE connection stayed alive throughout *and* through the
  subsequent BLE-triggered Wi-Fi stop — confirming the deliberate
  BLE+Wi-Fi-coexistence exception (see "BLE-triggered Wi-Fi" above)
  actually works, not just that it doesn't crash.
- **BLE file transfer**, from the same real central: fetched the file
  listing (data files first, then logs, both sorted), created a session
  over BLE and confirmed the new file appeared in a re-fetched listing,
  downloaded a 65 KB actively-growing log file and confirmed it matched a
  known-good copy byte-for-byte, downloaded a session data file and
  confirmed its size matched the listing exactly, confirmed an
  out-of-range index returns an empty download rather than garbage or a
  crash, and confirmed erase clears every data and log file except the
  one currently being written to. Five real bugs found and fixed getting
  here — see the numbered list below (11-15).
- **`tools/ble_cli.py`**, every command, against the real device: `info`,
  `status` (both a single read and `--watch`'s live notify stream),
  `profile` read and `--set`, `start`/`mark`/`stop` (status correctly
  reflected each), `lane-rotate`/`lane-set`/`race-toggle` (profile
  correctly reflected each — not status, which doesn't carry lane/race),
  `wifi-start` (polled correctly through the several-second real connect)
  and `wifi-stop`, `list-files`, and `download` — the downloaded file
  decoded cleanly with `tools/decode_log.py` and showed the exact
  `race`/`lane` values set moments earlier via the same CLI run. Two bugs
  found and fixed in the tool itself: a double-connect (manually calling
  `client.connect()` then also entering it as an `async with` context,
  which does the same thing again) that made every command fail
  immediately, and `lane-rotate`/`race-toggle` printing `status` instead
  of `profile` afterward — showing nothing useful, since lane/race aren't
  in the status characteristic at all.
- `fatal_handler.py`'s crash pipeline: caught and persisted a real
  `MemoryError` (see below) to `/syslog/crashes/` exactly as designed.
- **Beeper, audibly**: with the fixes below, all 12 named patterns
  (`boot_ready`, `wifi_connected`, ..., `reset_confirmed`) were played on
  the live device and confirmed heard as distinct tones with silent gaps
  between them — no clicking, no dropouts.
- **Physical button presses**: with the GP16/GP22 pin fix (see below), a
  real press of Button A logged "Recording ON" and opened a session file;
  Button B logged "Lap marker armed"; a second press of Button A logged
  "Recording OFF" and closed the session. The resulting file was pulled
  off the device and decoded — exactly one marker row, in the right
  position, with the rest of the data intact.
- **Frozen `./build.sh` build — Docker built, flashed, and boot-verified**
  for the first time (every earlier mention of this build mode says
  "untested — no Docker available"; that's no longer true). Two Docker
  permission bugs fixed to get there (see below). With `boot.py` and every
  `src/` module `manifest.py` freezes actually removed from the
  filesystem (not just present alongside their frozen copies — MicroPython
  resolves `/src` before `.frozen` in `sys.path`, so a leftover filesystem
  copy silently shadows the frozen one and defeats the whole point):
  measured **131968 bytes free RAM** at the start of `_main()`, vs ~91808
  under the unfrozen deploy tested earlier — **+40 KB (43%) more
  headroom**, with no import errors and the pre-log `errbuf`/reset-cause
  path (which depends on frozen `boot.py` specifically) working correctly.
- **Wi-Fi + BLE + web server + the ADC pipeline, sustained, under the
  frozen build**: not just the short round-trip above — a `bleak` central
  started Wi-Fi over BLE, then polled status every 5 s for **90
  continuous seconds** with all four subsystems live (ADC publishing
  throughout), before stopping Wi-Fi over BLE again. Zero disconnects,
  zero failed reads. One non-fatal warning observed once, right after the
  Wi-Fi-stop command (`BLE status notify failed: can't convert NoneType
  to int`, caught by the existing exception handler, self-recovered on
  the next 2 s status cycle) — not chased down further, noted here rather
  than silently dropped. This is real evidence the extra frozen-build
  headroom helps the exact combination the boot-time BLE-as-fallback
  policy exists to avoid, but it exercised the *dynamic*
  `CMD_WIFI_START`/`CMD_WIFI_STOP` path (see "BLE-triggered Wi-Fi"), not
  the boot-time policy itself — that policy is unchanged and still untested
  under a frozen build (see "What's still unverified").

**Found and fixed on hardware** (fifteen issues; the first three share a
root cause — this board has 264 KB of RAM and no headroom to spare):

1. Importing `ble_server` then `webserver` back-to-back with no
   `gc.collect()` raised `MemoryError` — `microdot.py` is one large
   (~2000-line) module and compiling it live needs a big contiguous
   allocation a fragmented heap can't satisfy. Fixed with `gc.collect()`
   immediately before each heavy import.
2. That fix wasn't sufficient once Wi-Fi *and* BLE *and* the ADC pipeline
   were all genuinely active simultaneously (not just fragmentation — real
   concurrent memory pressure). Fixed by precompiling `microdot.py` and
   `webserver.py` to `.mpy` bytecode with `mpy-cross` (committed under
   `pico/lib/microdot/microdot.mpy` and `pico/src/webserver.mpy` —
   `dist_manifest.py` ships these instead of the `.py` source; regenerate
   after editing either source per the comments there).
3. Even precompiled, running the Wi-Fi web server and BLE GATT server
   *concurrently* still sat right at this board's capacity under a
   non-frozen deploy. Rather than keep shaving bytes, `main.py` now treats
   BLE as a **fallback**: it only starts if Wi-Fi isn't configured or fails
   to connect, never alongside a working web UI. A frozen `./build.sh`
   build should have more headroom (frozen modules don't need this
   precompile trick, or the live-compile RAM spike at all) and might lift
   this restriction, but that hasn't been measured — see "still
   unverified" below.
4. **Button presses had no effect** — GP15/GP17 (Button A/B in the initial
   design) turned out to be unconnected on this board. This project's pin
   choices had wrongly copied the *unrelated* Pico 2 W reference board's
   button pins instead of this device's actual physical wiring. Confirmed
   by watching raw pin state on the live device while pressing each
   button: GP16 and GP22 are the real ones (matching the earlier
   prototype's own hardware notes, which documented this correctly all
   along — GP16 black / GP22 yellow). Fixed in `main.py`, `CONFIG.py`
   (`REBOOT_BUTTON_PIN`), and `factory_reset.py`'s default pin.
5. **Beeper was completely silent** — `PWM.freq()` rewrites the whole PWM
   CSR register as a side effect of reprogramming the clock divider,
   clearing the INVB (push-pull invert) bit set at construction. Since
   every note change calls `.freq()`, the invert was cleared on the very
   first note and never restored: both channels ended up driven in phase,
   and the differentially-wired piezo saw ~zero net voltage swing. Fixed
   by re-asserting INVB after every `.freq()` call, not just once at
   construction (confirmed via a direct CSR register readback on
   hardware, not just by ear).
6. **Beeper clicked instead of sounding "silence" between notes** — the
   fix for #5 briefly used a low (10 Hz) "quiet" frequency for the gaps
   between notes, which is audible as clicking, not silence. Tried
   silencing via `duty_u16(0)`/`duty_u16(32768)` toggling instead, which
   made things *worse*: it left the slice unable to produce a proper
   sustained tone afterwards (every note became a single click instead of
   holding pitch) for reasons not fully root-caused. Settled on the
   simplest thing confirmed to work cleanly on hardware: duty is set once
   at construction and never touched again; "silence" is 20 kHz (above
   typical adult hearing) instead of a low audible frequency — `_tone()`
   only ever calls `.freq()`.
7. **BLE lane/race commands changed state but the profile characteristic
   didn't reflect it** — `CMD_LANE_ROTATE`/`CMD_LANE_SET`/`CMD_RACE_TOGGLE`
   mutate the `PROFILE` singleton directly; the profile characteristic's
   *stored* value only got refreshed by `_profile_task`, which only runs
   when a central writes JSON to that characteristic — a different path
   these commands never touch. A central reading profile right after one
   of these commands saw stale data. Fixed by adding
   `BLEServer.refresh_profile()` and having `main.py` call it after each
   of the three mutations; confirmed fixed by the same `bleak` script
   reading back the actual new lane/race values afterward.
8. **`make sync` silently never updated an already-deployed device** —
   `mpremote fs cp -r pico/src :src` copies *into* `:src` when it already
   exists (true for any device past its first `make deploy`), landing the
   new files at `:src/src/*` while the real, imported `:src/*` stayed
   untouched. Every other file-content check in this bring-up log worked
   because it happened right after a fresh `make deploy`; this one didn't
   surface until iterating with `make sync` against an already-deployed
   board while testing the BLE control expansion. Fixed to match
   `deploy`'s already-correct pattern — `cp -r` into the *parent* (`:`),
   letting the local directory's own basename become the top-level name —
   confirmed by re-running `make sync` and checking `:src`/`:tests` came
   back flat.
9. **Frozen build failed at the freeze step: "Permission denied" reading
   the staged manifest** — `mattrmansfieldtx/micropython-builder` runs as
   a non-root container user (uid 1001, "app"), but `build.sh`'s
   `mktemp -d` staging directory is mode `0700` (owner-only), unreadable
   by a different uid even on a bind mount. Never caught before since
   Docker wasn't available to actually run this path. Fixed with
   `chmod -R a+rX "$STAGING_DIR"` right after writing the resolved
   manifest into it.
10. **Frozen build then failed copying artifacts out: "Permission denied"
    writing `output/`** — same root cause as #9, the other direction:
    `mkdir -p output`'s default mode (`0755`, owner-writable only) doesn't
    let the container's non-root user write `firmware.uf2` etc. into the
    bind-mounted host directory. Fixed with `chmod a+rwx output` right
    after creating it.
11. **BLE task crashed at boot the moment the Files service was added:
    `ValueError: Advertising payload too long`** — BLE's legacy
    advertising payload is capped at 31 bytes total, and each 128-bit
    custom service UUID costs 16 of them; the existing Logger service's
    UUID plus a second one for Files already blew the budget once the
    device name and other fields were added. Fixed by not advertising
    Files at all — a connected central still finds it via normal GATT
    service discovery regardless of what's in the advertisement, so
    nothing was actually lost.
12. **A 3rd characteristic on the Files service silently failed to
    register** — real GATT discovery from a `bleak` central showed only 2
    of the 3 characteristics originally defined (Logger's 3 registered
    fine), pointing at a total-GATT-attribute-count ceiling on this
    MicroPython BLE build rather than a per-service limit. Fixed by
    redesigning down to 2 characteristics — folding "advance" and "select
    a file" into the same write characteristic, distinguished by payload
    shape (see "BLE file transfer" above) — rather than chasing the
    actual ceiling number.
13. **A 7-file JSON listing truncated mid-value and failed to parse** —
    a single GATT attribute value is capped at 512 bytes by the BLE spec
    itself; a flat listing character grows past that once there are more
    than a handful of files. Fixed by routing the listing through the
    same chunked transfer path as a real file download instead of its own
    cached characteristic (see #12's redesign — same fix covered both).
14. **Selecting a file by name silently failed — a real central defaulted
    to the BLE-spec MTU minimum (23, a 20-byte write payload) and stayed
    there even after the device explicitly requested a larger one on
    connect** (`connection.exchange_mtu(247)` sent without error; a real
    `bleak`/BlueZ central just didn't honour it). Real filenames
    (`session_*.bin` is 27 characters, `log_*.log` is 23) don't reliably
    fit in 20 bytes, and MicroPython's bluetooth stack doesn't implement
    the GATT "queued write" fallback BLE defines for oversized single
    writes — the write silently landed truncated
    (`"log_20210101_000003."`, missing `.log`) instead of raising an
    error. Fixed by redesigning selection to be by index into the most
    recently fetched listing (3 bytes, fits any MTU) rather than by name,
    instead of chasing MTU negotiation further.
15. **File downloads intermittently corrupted — not dropped or duplicate
    chunks, but content from a *different, later* point in the file
    spliced into the middle of an earlier one** — reading `FILE_CHUNK`
    immediately after writing the "advance" command, with no delay,
    raced the device's own buffer update (a torn read of `_file_chunk`'s
    value, serving a read partway through `_prepare_chunk()` overwriting
    it). Reproducible at ~20ms between write and read on a 65 KB file;
    confirmed clean at ~150ms on the same file and device state. Fixed by
    documenting a 100ms minimum pacing requirement between "advance" and
    the next read, rather than patching aioble/MicroPython's BLE stack
    internals directly.

**Operational lesson for future debugging on this board**: interrupting a
running Wi-Fi/BLE session with Ctrl-C (`mpremote ... resume exec`) rather
than a real hardware reset (`machine.reset()`, or reconnecting *without*
`resume` to get mpremote's DTR-toggle reset) does not cleanly tear down
lwIP sockets or CYW43 state. Several apparent bugs during this bring-up
(spurious `ENOMEM` on a bare `asyncio.start_server()`, a phantom
`TypeError` that didn't reproduce) turned out to be resource leakage from
repeated Ctrl-C interrupts, not real defects — always verify a suspicious
hardware failure against a *genuinely* clean reset before trusting it.

### What's still unverified

- **The boot-time BLE-as-fallback policy itself, under a frozen build** —
  `_main()` still never starts Wi-Fi and BLE together at boot regardless
  of build mode (see "BLE is a fallback at boot" in `CLAUDE.md`), and
  that policy hasn't been re-tested now that frozen measurably has ~40 KB
  more headroom (see "What's verified on hardware"). The *dynamic*
  BLE-triggered Wi-Fi start (which deliberately does run both together)
  was sustained-tested under frozen and held up for 90 s — that's
  evidence the combination itself is more comfortable now, but it isn't
  the same code path as the boot-time decision, which remains
  conservative on purpose.
- A clean frozen-vs-unfrozen **flash budget** (free littlefs bytes)
  comparison — the frozen build was flashed to a device already carrying
  test-session cruft (accumulated syslogs, a stray directory from
  unrelated testing), confounding a fair before/after measurement. See
  "Flash budget" above for what could and couldn't be concluded from it.
- `CONFIG.WIFI_MIN_FREE_BYTES`'s safety margin under longer than the ~90 s
  sustained Wi-Fi+BLE+ADC test performed here (see "What's verified on
  hardware") — that test held up with no disconnects and only one
  self-recovering non-fatal warning, but a threshold picked by judgement
  rather than a stress test to failure could still be wrong for longer
  sessions, more BLE traffic, or heavier web UI use than this test drove.

---

## Session binary format

One file per Button-A on/off cycle under `/data`, `session_YYYYMMDD_HHMMSS.bin`:

```
[header: magic 'SCL1', version, start_epoch, sample_rate_hz, profile JSON]
[record]*    8 bytes each: dt_ms(u16), current_cA(i16), track_cV(u16), supply_cV(u16)
```

A lap marker (Button B) is a record with `current_cA == -32768`. Convert to
CSV or a pandas DataFrame with `tools/decode_log.py`:

```bash
python3 tools/decode_log.py session_20260101_120000.bin -o session.csv
python3 tools/decode_log.py session_20260101_120000.bin --pandas
```

Or fetch it straight from the device over the web UI — every session in the
list has a `csv` download link that runs the same conversion on-device.

---

## Visualizing a session (LibreOffice)

`tools/graph_session_csv.bas` graphs a decoded session CSV inside LibreOffice
Calc — no separate plotting tool needed. Three steps: reduce the binary log
to CSV, install the macro once, then run it against any session.

### 1. Reduce the data

Same conversion as above — pull the session off the device (or copy it from
`/data` some other way) and decode it to CSV on a host machine:

```bash
python3 tools/decode_log.py session_20260101_120000.bin -o session.csv
```

### 2. Install the macro

One-time setup, in LibreOffice Calc:

1. `Tools > Macros > Edit Macros...` to open the Basic IDE.
2. In the object tree on the left, under **My Macros > Standard**, right-click
   and insert a new module (or reuse an empty default one).
3. Open `tools/graph_session_csv.bas` in a text editor, copy the whole file,
   and paste it into the new module, replacing any placeholder content.
4. Save. Installing it under **My Macros** (rather than inside the document)
   makes it available to any spreadsheet you open afterwards, not just the
   one open at the time.

### 3. Display the graphs

1. Open the decoded `session.csv` in LibreOffice Calc.
2. `Tools > Macros > Run Macro...`, find `GraphSessionCSV` under
   **My Macros > Standard**, and run it (or press F5 from inside the Basic
   IDE with that Sub selected).

This builds a chart named `SessionChart` next to the data:

- **X axis**: `t_ms`.
- **Left axis** ("track current"): `current_A`, in yellow. Range is dynamic —
  floored/ceiled to the nearest whole amp from the session's actual min/max,
  not a fixed scale, so a mild session isn't flattened and a hard one isn't
  clipped.
- **Right axis** ("supply and track voltages"): `track_V` (red) and
  `supply_V` (blue), 0 up to the session's real peak volt, rounded up to the
  next whole volt.
- **Lap markers**: each Button-B press (the CSV's `marker` column) draws as
  a black vertical line spanning the current axis, labelled "lap marker" in
  the legend.

Re-running `GraphSessionCSV` — e.g. after re-decoding an updated session over
the same CSV — replaces the existing `SessionChart` rather than piling up
duplicates, so it's safe to run again.

---

## Buttons and beeper

| Button | Action |
|--------|--------|
| A / black (GP16) | Toggle capture on/off (new session file per on/off cycle); held at power-on: factory reset |
| B / yellow (GP22) | Lap marker — only while capturing |

| Beeper pattern | Meaning |
|-----------------|---------|
| Rising 3-note | Boot ready |
| Two ascending notes | Wi-Fi connected |
| Two low notes | Wi-Fi connect failed |
| Two-note chirp | BLE central connected |
| Single high note | Capture started |
| Single mid note | Capture stopped |
| Very short high blip | Lap marker |
| Two-note warble | Flash getting low |
| Three low notes | Flash full — capture stopped |
| Three low notes, repeating | Fatal error (repeats until auto-reboot) |
| Short tick, once per second | Factory-reset countdown (Button A held at boot) |
| Two descending notes | Wi-Fi stopped (BLE command) |
| Two-note up-blip | Lane or race type changed (BLE command) |
| Same low note, twice | Sessions erased (BLE command) |
| Single low, held note | BLE command rejected (still recording, lane out of range, or not enough free heap for Wi-Fi) |

---

## Abbreviated UI

- **Web** (Wi-Fi): status, Start/Stop/Mark, session list with raw or CSV
  download, erase-all, a profile form (track/race/lane/controller/car), and
  an optional `/ws` feed of plain numeric readings — no live graph.
- **BLE**: a Device Information service (with the current IP address folded
  into the firmware-revision characteristic, so a phone paired over BLE but
  not on the same Wi-Fi can still find the web UI), a custom Logger service
  with status (notify), control (write, one byte per command — see table
  below), and profile (read/write/notify) characteristics, and a Files
  service to list and download session data and syslog files (see "BLE
  file transfer" below) — a BLE-only equivalent of the web UI's session
  list/download/erase, for when there's no Wi-Fi to reach that with.

BLE is a **fallback at boot**, not started alongside a Wi-Fi connection
that's already up: it only starts if Wi-Fi isn't configured or fails to
connect. Confirmed on hardware that running Wi-Fi + BLE + the ADC pipeline
all at once is right at this 264 KB-RAM board's capacity under a non-frozen
deploy — see "What's verified on hardware" for the measurements this is
based on. Most tracks have no Wi-Fi at all (per the earlier prototype's own
notes), so BLE covers exactly the case where it matters.

### BLE control characteristic

One byte per command, written to the Logger service's control
characteristic (`CMD_LANE_SET` takes a second payload byte):

| Byte | Command | Notes |
|------|---------|-------|
| 0 | Stop capture | |
| 1 | Start capture | new session file |
| 2 | Lap marker | only while capturing |
| 3 | Erase all sessions and logs | refused (`command_rejected` beep) if still capturing; download anything worth keeping first (see "BLE file transfer") — this doesn't ask twice |
| 4 | Start Wi-Fi | see "BLE-triggered Wi-Fi" below |
| 5 | Stop Wi-Fi | tears down the web server, back to BLE-only |
| 6 | Rotate lane | advances to the next lane colour, wraps after the last one |
| 7 | Set lane | byte 2: lane number, 1-8 |
| 8 | Toggle race type | flips `practice` <-> `race` |

Lane and race changes go through the same `session_profile.py` `PROFILE`
singleton the web UI's profile form and BLE's profile characteristic
already use, so they're persisted and reflected there too, not a separate
side channel.

### BLE-triggered Wi-Fi

Commands 4/5 are a deliberate, narrow exception to "BLE is a fallback"
above: unlike the boot-time path, starting Wi-Fi from a running BLE
connection keeps BLE alive afterwards rather than stopping it — the
assumption being that a driver who just asked for Wi-Fi over BLE probably
still wants BLE control (not least to stop Wi-Fi again). Since that
means Wi-Fi *can* end up running alongside BLE — the exact combination
the boot-time fallback exists to avoid — command 4 first checks free heap
against `CONFIG.WIFI_MIN_FREE_BYTES` and refuses (beeping
`command_rejected`) rather than risking a `MemoryError` if it's not met.
That threshold is a judgement call, not a hardware measurement — see
"What's still unverified".

### BLE file transfer

A BLE-only Files service (separate from the Logger service above) lists
and downloads session data (`.bin`) and syslog (`.log`) files — the way
to get data off the device with no Wi-Fi to reach the web UI's own
session list/download. Two characteristics, both arrived at the hard way
on real hardware (see the "found and fixed" log below for the full
story of each):

- **Selection is by index into the listing, not filename.** Real
  filenames (`session_YYYYMMDD_HHMMSS.bin` is 27 characters,
  `log_YYYYMMDD_HHMMSS.log` is 23) don't reliably fit in a single BLE
  write — the guaranteed-minimum ATT MTU is 23 bytes (20 usable payload
  bytes), and a real central stayed there even after the device asked for
  a bigger one. A 3-byte index-based select sidesteps needing MTU
  negotiation to work at all.
- **The listing itself streams through the same chunked path as a real
  file**, rather than its own cached characteristic — a flat JSON listing
  blows past the BLE spec's 512-byte single-attribute-value cap once
  there are more than a handful of files, which any device that's been
  in use for a while will have.

Wire protocol, writing to `FILE_SELECT` and reading `FILE_CHUNK` (empty
chunk = done):

1. Write `0x01` to `FILE_SELECT` (fetch the listing).
2. Read `FILE_CHUNK`. **Wait at least 100ms**, write `0x00` to
   `FILE_SELECT` (advance), repeat until a chunk comes back empty —
   confirmed on hardware that reading back-to-back with no delay
   intermittently corrupts the data (a torn read racing the device's
   buffer update, not a dropped chunk — see the log below). What you've
   reassembled is JSON: `[{"name", "kind": "data"|"log", "size"}, ...]`,
   in a fixed order (data files first, then log files, each sorted).
3. To download one, write `0x02` + its position in that list as a
   little-endian `u16` (3 bytes total) to `FILE_SELECT`, then repeat step
   2's read/wait/advance loop to pull its contents.

Erasing (control command 3) clears every session and log file except the
one currently being written to — download first if you want to keep
anything, since erase doesn't ask twice.

### BLE command-line client

`tools/ble_cli.py` is a ready-to-use command-line client for everything
above — status, capture/erase/Wi-Fi/lane/race control, profile
read/write, and file listing/download — so a phone app isn't the only
way to drive the device over BLE:

```bash
pip install bleak
python3 tools/ble_cli.py scan                    # find nearby devices
python3 tools/ble_cli.py status                  # or --watch for live updates
python3 tools/ble_cli.py start                   # stop / mark / erase
python3 tools/ble_cli.py wifi-start               # polls up to 15s for the connect
python3 tools/ble_cli.py lane-rotate              # or lane-set 5 / race-toggle
python3 tools/ble_cli.py profile                  # or --set track=Daytona --set lane=3
python3 tools/ble_cli.py list-files
python3 tools/ble_cli.py download session_20260101_120000.bin
```

Every command re-scans by default (`--timeout` to adjust); pass
`--address` (from `scan`'s output) to connect directly once you know it,
skipping the scan. Implements the exact wire protocol above — UUIDs and
command bytes are copied from `ble_server.py`, not imported (host tool,
device code — keep the two in sync by hand if either changes).

### Flutter mobile app

`app/` is a Flutter client for iOS and Android implementing the same BLE
protocol as `ble_cli.py` above: scan for `SCLogger-*` devices, connect,
live status, start/stop/mark/erase, Wi-Fi start/stop, lane rotate/set,
race toggle, profile view/edit, and file list/download (downloaded files
are handed to the OS share sheet, since phones have no meaningful
"current directory" for the user to find them in). Uses
[`flutter_blue_plus`](https://pub.dev/packages/flutter_blue_plus) for BLE;
its `connect()` call requires declaring a use-case license, and this app
uses `License.nonprofit` (`app/lib/ble_service.dart`) — correct for a
personal/hobby project, but worth knowing about if this code is ever
reused for something commercial.

```bash
cd app
flutter pub get
flutter run              # needs a connected/emulated phone
```

### Android build (Docker)

`app/build-android.sh` builds the Android APK inside
[`ghcr.io/cirruslabs/flutter`](https://github.com/cirruslabs/docker-images-flutter),
a self-contained image with its own Flutter SDK, Android SDK, NDK, and
pre-accepted licenses. This exists because building against this
project's host Android SDK (a shared, root-owned install) needed three
separate `sudo chown` passes to get writable — see "What's verified"
below. The container needs none of that:

```bash
cd app
./build-android.sh              # debug (default)
./build-android.sh release      # release, signed with the debug keystore
```

Output lands at `app/build-out/app-<mode>.apk`. First run pulls the base
image (several GB); after that only the app layer rebuilds. Confirmed on
this machine: `flutter pub get` + `analyze` + `test` + `build apk --debug`
all pass inside the container, producing a real, installable APK — same
outcome as the host build, without touching `/opt/android-sdk` at all.

iOS has no equivalent — Xcode only runs on macOS, so no Docker image (on
Linux, at least) can produce an iOS build. That needs a real Mac or a
cloud CI service that provisions Apple hardware (Codemagic and GitHub
Actions' `macos-latest` runners both work for Flutter).

Key files:

- `lib/ble_protocol.dart` — UUIDs, command bytes, and payload
  (de)serialization. Hand-copied from `pico/src/ble_server.py` (same
  relationship as `ble_cli.py` above — not imported, kept in sync by hand).
- `lib/ble_service.dart` — the `flutter_blue_plus` wrapper (scan, connect,
  status/profile/control, chunked file transfer with the same 150ms
  pacing `ble_cli.py` uses).
- `lib/scan_screen.dart`, `lib/dashboard_screen.dart`, `lib/files_screen.dart`
  — the three screens.

**What's verified**: `flutter analyze` and `flutter test` both pass clean,
and `flutter build apk --debug` succeeds — both directly against this
machine's host Android SDK and inside the Docker image above — producing
a real, installable `app-debug.apk` either way. Two environment quirks
worth knowing about if this is rebuilt elsewhere:

- `compileSdk` here tracks Flutter's default rather than the
  `permission_handler_android` plugin's, because that plugin's 14.0.0
  release hardcodes `compileSdk 37` and only a `37.0`-suffixed preview
  build of that platform exists in the SDK repo (no bare `android-37`
  yet) — see `pubspec.yaml`'s `dependency_overrides` pinning
  `permission_handler_android` back to 12.0.13 (`compileSdk 34`) instead.
- `pubspec.yaml`'s `environment: sdk:` is `^3.12.0`, not the `^3.12.2`
  that `flutter create` originally pinned to the host's exact Dart
  version — the Docker image ships Dart 3.12.0, and nothing here actually
  needs 3.12.2's specific features, so the constraint was relaxed rather
  than chasing a matching container image.

**What's not verified**: no physical iPhone or Android phone was available
in the development environment (only the Pico W itself, over USB serial),
and iOS builds are categorically impossible without a Mac/Xcode. The app
has not been installed or exercised against a real BLE connection — only
the protocol logic and the fact that it compiles into a real APK, mirroring
`ble_cli.py`'s already hardware-verified implementation line for line.
Treat it as implemented-and-builds-but-runtime-untested until someone
installs it on an actual phone.

---

## References

- Peter Hinch async primitives: <https://github.com/peterhinch/micropython-async>
- Microdot: <https://github.com/miguelgrinberg/microdot>
- RP2040 datasheet (PWM push-pull, ADC): <https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf>
- The Pico 2 W reference this project downgrades: <https://github.com/aartech-dev/logger>
