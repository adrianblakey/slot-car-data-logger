# Copyright @ 2026 Adrian Blakey. All rights reserved
# manifest.py — frozen module manifest for the Pico W Slot Car Logger.
#
# Place this file in the repository root alongside Dockerfile and build.sh.
# Passed to the MicroPython build system via FROZEN_MANIFEST.
# Reference: https://docs.micropython.org/en/latest/reference/manifest.html
#
# ── What to freeze and what NOT to freeze ─────────────────────────────────
#
# MUST NOT be frozen (kept on the device filesystem):
#   BOOT.py    — Wi-Fi start flag + fallback SSID/password. Must be editable
#                without reflashing firmware.
#   CONFIG.py  — MODE ("debug"/"production"), sample rate, flash quota
#                floors. Must be editable without reflashing firmware.
#   main.py    — kept on filesystem so it can be updated without a full
#                reflash; a frozen main.py causes confusion (the filesystem
#                copy silently takes priority).
#
# Vendored third-party libraries (primitives/, microdot/, logging.py) also
# stay on the filesystem rather than frozen — they're plain files under
# /lib either way (MicroPython's default sys.path already includes /lib),
# and keeping them off the frozen image means they can be updated the same
# way as everything else in dist_manifest.py's LIB section, via `make deploy`.

# ── Board defaults — CRITICAL, must come first ─────────────────────────────
# FROZEN_MANIFEST *replaces* the board manifest rather than extending it.
# Without this include, the build silently loses everything the board
# normally freezes: the complete asyncio package (funcs.py providing
# wait_for/gather), the Pico W networking + Bluetooth bundle (aioble,
# bluetooth, the CYW43 driver), and the rp2 port modules. Symptom of its
# absence: boot works but the first asyncio.wait_for/aioble import dies.
include("$(BOARD_DIR)/manifest.py")

# ── MicroPython stdlib modules ──────────────────────────────────────────────
require("errno")

# ── boot.py: freeze the boot sequence ───────────────────────────────────────
# Stable and benefits from being frozen (faster boot, less RAM). A newer
# filesystem copy still takes priority if one is deployed.
freeze("$(APP_DIR)", "boot.py")

# ── Application src/ modules ─────────────────────────────────────────────────
# Excludes: BOOT.py, CONFIG.py (see above), test scripts.
freeze("$(APP_DIR)/src", (
    # ADC / Core 1
    "adc_device.py",
    "log_record.py",

    # Storage / logging
    "flash_writer.py",
    "session_profile.py",
    "error_buffer.py",
    "logconfig.py",

    # Crash handling
    "crash_report.py",
    "fatal_handler.py",
    "factory_reset.py",

    # User feedback
    "buzzer.py",

    # Connectivity
    "wifi_connection.py",
    "ble_server.py",
    "webserver.py",
))
