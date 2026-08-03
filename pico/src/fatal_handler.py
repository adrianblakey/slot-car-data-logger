# Copyright @ 2026 Adrian Blakey. All rights reserved
# fatal_handler.py — no-display fatal-error handling.
#
# The Pico 2 W reference escalates fatal errors to a CrashScreen widget.
# This board has no display, so the "screen" is a repeating beeper pattern
# (fatal_error(), replayed every few seconds until reboot) plus the syslog
# and a persisted crash-report JSON — both readable later over the web UI
# (webserver.py serves the crash report list and the current syslog).

import sys
import time
import asyncio

from crash_report import write_report

try:
    from CONFIG import CRASH_PERSIST_JSON, CRASH_AUTO_REBOOT_MS
except Exception:
    CRASH_PERSIST_JSON = True
    CRASH_AUTO_REBOOT_MS = 120_000

_beeper = None   # set via configure(beeper) once main.py has one


def configure(beeper) -> None:
    global _beeper
    _beeper = beeper


async def handle_fatal(exc: Exception, log, source: str = "Core0") -> None:
    """Log -> persist crash report -> repeat beeper pattern -> auto-reboot."""
    import io
    buf = io.StringIO()
    sys.print_exception(exc, buf)
    trace = buf.getvalue()

    try:
        log.critical("[%s] FATAL: %s", source, trace)
        for h in getattr(log, "handlers", []):
            try:
                h.flush()
            except Exception:
                pass
    except Exception:
        pass

    if CRASH_PERSIST_JSON:
        try:
            write_report(type(exc), exc, trace)
        except Exception:
            pass

    import machine
    timeout = CRASH_AUTO_REBOOT_MS or 120_000
    deadline = time.ticks_add(time.ticks_ms(), timeout)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if _beeper is not None:
            try:
                _beeper.fatal_error()
            except Exception:
                pass
        await asyncio.sleep_ms(3000)
    machine.reset()
