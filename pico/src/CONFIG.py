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
