# Copyright @ 2026 Adrian Blakey. All rights reserved
# flash_writer.py — session lifecycle + flash quota guard.
#
# One binary log_record.py file per Button-A on/off cycle, written under
# /data (created on first use) on the internal flash filesystem. There is no
# SD card to fail over to on this board, so running low is handled by
# stopping (the safe default) or, if CONFIG.FLASH_AUTO_ROTATE is explicitly
# enabled, deleting the oldest session file(s) to make room.
#
# time.ticks_us()/ticks_diff() are MicroPython-only; _ticks_diff() below
# falls back to plain subtraction on CPython so this module (and its dt_ms
# bookkeeping) is exercised directly by the host test suite instead of only
# through hardware-dependent mocks.

import os
import time

import log_record as lr
from session_profile import PROFILE

try:
    from CONFIG import FLASH_MIN_FREE, FLASH_LOW_WARN, FLASH_AUTO_ROTATE
except Exception:
    FLASH_MIN_FREE = 64 * 1024
    FLASH_LOW_WARN = 192 * 1024
    FLASH_AUTO_ROTATE = False

DATA_DIR = "/data"
_EXT = ".bin"

try:
    _ticks_diff = time.ticks_diff
except AttributeError:
    def _ticks_diff(a, b):
        return a - b


def _free_bytes(path="/"):
    """os.statvfs wrapper — its own function so tests can monkeypatch it."""
    st = os.statvfs(path)
    return st[0] * st[3]     # f_bsize * f_bfree


def ensure_data_dir(data_dir=DATA_DIR):
    try:
        os.mkdir(data_dir)
    except OSError:
        pass  # already exists


def list_sessions(data_dir=DATA_DIR):
    ensure_data_dir(data_dir)
    return sorted(f for f in os.listdir(data_dir) if f.endswith(_EXT))


def erase_all(data_dir=DATA_DIR):
    """Delete every session file. Returns the count removed."""
    n = 0
    for f in list_sessions(data_dir):
        os.remove(data_dir + "/" + f)
        n += 1
    return n


def _rotate_oldest(data_dir=DATA_DIR):
    """Delete the single oldest session file. Returns True if one existed."""
    sessions = list_sessions(data_dir)
    if not sessions:
        return False
    os.remove(data_dir + "/" + sessions[0])
    return True


class FlashQuotaError(Exception):
    pass


class FlashWriter:
    """
    One instance manages ONE session file's lifecycle:
        start() -> write_sample()/write_marker() (any number, interleaved)
        -> close()
    """

    def __init__(self, data_dir=DATA_DIR, sample_rate_hz=200):
        self._data_dir = data_dir
        self._sample_rate_hz = sample_rate_hz
        self._file = None
        self._fname = None
        self._last_t = None
        self._n_records = 0

    def is_open(self):
        return self._file is not None

    def filename(self):
        return self._fname

    def record_count(self):
        return self._n_records

    # ── quota ──────────────────────────────────────────────────────────────
    @staticmethod
    def free_bytes(path="/"):
        return _free_bytes(path)

    @staticmethod
    def quota_state(path="/"):
        """'ok' | 'low' | 'full' against the CONFIG floors."""
        free = _free_bytes(path)
        if free < FLASH_MIN_FREE:
            return "full"
        if free < FLASH_LOW_WARN:
            return "low"
        return "ok"

    # ── session lifecycle ─────────────────────────────────────────────────
    def start(self, start_epoch=None):
        if self._file is not None:
            raise RuntimeError("session already open")

        state = self.quota_state()
        if state == "full":
            if FLASH_AUTO_ROTATE and _rotate_oldest(self._data_dir):
                state = self.quota_state()
            if state == "full":
                raise FlashQuotaError(
                    "flash below floor ({} bytes free)".format(self.free_bytes()))

        ensure_data_dir(self._data_dir)
        if start_epoch is None:
            start_epoch = int(time.time())
        t = time.localtime(start_epoch)
        fname = "{}/session_{:04d}{:02d}{:02d}_{:02d}{:02d}{:02d}{}".format(
            self._data_dir, t[0], t[1], t[2], t[3], t[4], t[5], _EXT)

        f = open(fname, "wb")
        f.write(lr.pack_header(start_epoch, self._sample_rate_hz, PROFILE.as_json()))
        f.flush()

        self._file = f
        self._fname = fname
        self._last_t = None
        self._n_records = 0
        return fname

    def _dt_ms(self, t):
        """t is a monotonic tick value (time.ticks_us() on-device, any
        strictly-increasing int in tests). Returns ms since the previous
        record, 0 for the first one."""
        if self._last_t is None:
            dt_ms = 0
        else:
            dt_ms = _ticks_diff(t, self._last_t) // 1000
        self._last_t = t
        return dt_ms

    def write_sample(self, t, current_A, track_V, supply_V):
        if self._file is None:
            return
        dt_ms = self._dt_ms(t)
        self._file.write(lr.pack_record(dt_ms, current_A, track_V, supply_V))
        self._n_records += 1

    def write_marker(self, t, track_V=0.0, supply_V=0.0):
        if self._file is None:
            return
        dt_ms = self._dt_ms(t)
        self._file.write(lr.pack_marker(dt_ms, track_V, supply_V))
        self._n_records += 1

    def flush(self):
        if self._file is not None:
            self._file.flush()

    def close(self):
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None
