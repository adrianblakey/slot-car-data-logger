# Copyright @ 2026 Adrian Blakey. All rights reserved.
# CONFIG.py — build-mode constants
#
# MODE: "debug"      -> DEBUG logging, console output enabled, WDT disabled
#       "production" -> WARNING logging only, WDT armed
#
# Kept on the filesystem (never frozen) so it can be edited without a
# reflash.

MODE                 = "debug"
LOG_TO_CONSOLE       = True
LOG_TO_FLASH         = True

CRASH_PERSIST_JSON   = True
CRASH_AUTO_REBOOT_MS = 120_000   # 2 minutes
REBOOT_BUTTON_PIN    = 16        # held at boot -> factory reset (Button A's pin)

# ── ADC capture ────────────────────────────────────────────────────────────
# Published sample rate. See README "Flash budget" for the space/duration
# tradeoff — 8 bytes/record, so e.g. 200 Hz = 1.6 KB/s.
SAMPLE_RATE_HZ       = 200

# ── Flash quota guard (flash_writer.py) ─────────────────────────────────────
# Absolute free-space floor, in bytes, below which capture is stopped.
# Measured on real hardware (mpy build, unfrozen): the littlefs filesystem's
# usable space is ~848 KB total, ~468 KB free once this app's own files
# (main.py/boot.py/src/lib/conf/static, ~380 KB) are deployed — well under
# the ~1-1.5 MB assumed before hardware was available. Floors sized down
# accordingly; re-measure after a `./build.sh` frozen build, which should
# free up most of that 380 KB since app code moves into firmware.
FLASH_MIN_FREE       = 32 * 1024
FLASH_LOW_WARN       = 96 * 1024   # beeper "flash-low" warning threshold

# If True, flash_writer deletes the oldest session file(s) to make room when
# the floor is hit instead of just stopping. Off by default: silently
# deleting a driver's data is worse than telling them to unload it.
FLASH_AUTO_ROTATE    = False

# ── BLE-triggered dynamic Wi-Fi start ───────────────────────────────────────
# Free-heap floor main.py checks before starting Wi-Fi + the web server on a
# BLE "start Wi-Fi" command, refusing (and beeping command_rejected) rather
# than risking a MemoryError if it's not met. Unlike FLASH_MIN_FREE above,
# this is a judgement call, not a hardware measurement: the README's "What's
# still unverified" notes that Wi-Fi+BLE+web-server-together's headroom on a
# *frozen* build hasn't been measured, and this dynamic path deliberately
# keeps BLE running alongside Wi-Fi afterwards (unlike the boot-time path,
# which treats BLE as a strict fallback — see main.py). Tune this after
# testing the BLE-start path on real hardware.
WIFI_MIN_FREE_BYTES  = 40 * 1024

# ── BLE file transfer ────────────────────────────────────────────────────
# Bytes returned per FILE_CHUNK read (see ble_server.py's Files service). A
# judgement call, not a measured safe maximum: BLE's ATT_MTU is negotiated
# per connection, and a value must stay under (negotiated MTU - 3 bytes ATT
# header) or a read silently truncates. 180 stays safely under the ~247-byte
# MTU most modern centrals (phones, bleak) negotiate by default, with margin
# for less capable ones — but hasn't been stress-tested against a central
# that never negotiates past the BLE-spec default of 23.
BLE_FILE_CHUNK_SIZE  = 180
