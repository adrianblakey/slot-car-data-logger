# Copyright @ 2026 Adrian Blakey. All rights reserved
# crash_report.py — persists crash reports to internal flash (the only
# storage medium on this board).
#
# Storage is APPEND-ONLY, one file per crash (crash_0001.json ...), NOT a
# single rewritten JSON array: a read-modify-write scheme risks a fault (or
# power loss) mid-write truncating the file, and a corrupt read being caught
# as "start empty" would silently wipe all prior history. One file per crash
# means a bad write costs at most one report.
#
# Reused near-verbatim from the Pico 2 W reference (crash_report.py), which
# already targeted flash rather than the SD card for exactly this reason.

import json
import os
import time

MAX_REPORTS = 8
_DIR = "/syslog/crashes"


def _ensure_dir():
    for d in ("/syslog", _DIR):
        try:
            os.mkdir(d)
        except OSError:
            pass


def _report_files():
    try:
        return sorted(f for f in os.listdir(_DIR)
                      if f.startswith("crash_") and f.endswith(".json"))
    except OSError:
        return []


def write_report(exc_type, exc_value, traceback_text):
    """
    Append one crash report as its own file. Fail-soft and minimal-
    allocation: this runs inside the fatal path, where the heap may already
    be low, so it must never raise.
    """
    try:
        _ensure_dir()

        files = _report_files()
        if files:
            try:
                last = int(files[-1][6:10])
            except (ValueError, IndexError):
                last = len(files)
        else:
            last = 0
        path = "{}/crash_{:04d}.json".format(_DIR, last + 1)

        name = getattr(exc_type, "__name__", None) or str(exc_type)
        report = {
            "time": "{}".format(time.localtime()),
            "exception": str(name),
            "message": str(exc_value),
            "trace": traceback_text,
        }
        with open(path, "w") as f:
            json.dump(report, f)

        files = _report_files()
        for old in files[:-MAX_REPORTS]:
            try:
                os.remove("{}/{}".format(_DIR, old))
            except OSError:
                pass
    except Exception:
        pass   # never crash during crash reporting


def read_reports():
    """Return all stored reports, oldest first. Skips any unreadable file."""
    out = []
    for fn in _report_files():
        try:
            with open("{}/{}".format(_DIR, fn)) as f:
                out.append(json.load(f))
        except Exception:
            pass
    return out


def clear_reports():
    """Delete all stored crash reports."""
    for fn in _report_files():
        try:
            os.remove("{}/{}".format(_DIR, fn))
        except OSError:
            pass
