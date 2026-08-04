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

**Status:** built and host-tested (`make host-test`, 46 tests), then deployed
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
`static` — about 380 KB unfrozen). A frozen `./build.sh` build should claw
most of that 380 KB back since app code moves into firmware instead of the
filesystem, but that hasn't been measured yet.

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
  host found `SCLogger-e6614c`) when Wi-Fi isn't up — full GATT
  characteristic read/write from a client app wasn't tested, only
  advertisement discovery.
- `fatal_handler.py`'s crash pipeline: caught and persisted a real
  `MemoryError` (see below) to `/syslog/crashes/` exactly as designed.
- `buzzer.py` constructs its PWM objects and sets tones without raising —
  not confirmed audibly (no way to hear it remotely).
- **Physical button presses**: with the GP16/GP22 pin fix (see below), a
  real press of Button A logged "Recording ON" and opened a session file;
  Button B logged "Lap marker armed"; a second press of Button A logged
  "Recording OFF" and closed the session. The resulting file was pulled
  off the device and decoded — exactly one marker row, in the right
  position, with the rest of the data intact.

**Found and fixed on hardware** (four issues; the first three share a root
cause — this board has 264 KB of RAM and no headroom to spare):

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

- Beeper tones audibly, only that PWM calls don't raise.
- BLE GATT characteristic read/write from a real client app — only
  advertisement discovery was confirmed, not a full connection (and BLE
  now only runs when Wi-Fi is absent, so this needs a Wi-Fi-less test).
- Flash budget and the Wi-Fi+BLE-concurrently restriction under a
  **frozen** `./build.sh` build — only the unfrozen `make deploy` footprint
  has been measured; frozen modules don't pay the live-compile RAM cost
  this session's fixes work around, so a frozen build might not need the
  BLE-as-fallback restriction at all. Untested — no Docker available in
  this environment.

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

---

## Abbreviated UI

- **Web** (Wi-Fi): status, Start/Stop/Mark, session list with raw or CSV
  download, erase-all, a profile form (track/race/lane/controller/car), and
  an optional `/ws` feed of plain numeric readings — no live graph.
- **BLE**: a Device Information service (with the current IP address folded
  into the firmware-revision characteristic, so a phone paired over BLE but
  not on the same Wi-Fi can still find the web UI) and a custom Logger
  service with status (notify), control (write: start/stop/mark), and
  profile (read/write/notify) characteristics.

BLE is a **fallback**, not run alongside a working Wi-Fi connection: it
only starts if Wi-Fi isn't configured or fails to connect. Confirmed on
hardware that running both plus the ADC pipeline at once is right at this
264 KB-RAM board's capacity under a non-frozen deploy — see "What's
verified on hardware" for the measurements this is based on. Most tracks
have no Wi-Fi at all (per the earlier prototype's own notes), so BLE
covers exactly the case where it matters.

---

## References

- Peter Hinch async primitives: <https://github.com/peterhinch/micropython-async>
- Microdot: <https://github.com/miguelgrinberg/microdot>
- RP2040 datasheet (PWM push-pull, ADC): <https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf>
- The Pico 2 W reference this project downgrades: <https://github.com/aartech-dev/logger>
