# Copyright @ 2026 Adrian Blakey. All rights reserved.
# logconfig.py — logging initialisation for the Pico W Slot Car Logger.
#
# Adapted from the Pico 2 W reference: there is no SD card here, so the
# syslog always lives on internal flash (the reference already preferred
# flash for the syslog over the data medium — see its comment about littlefs
# reentrancy — so this is simply "always take that branch").
#
# Usage:
#   log = logconfig.configure("main")   # call once at startup
#   log = logconfig.get_logger("foo")   # call from any module after configure()

import os
import logging
import time

try:
    from CONFIG import MODE, LOG_TO_CONSOLE, LOG_TO_FLASH
except Exception:
    MODE           = "debug"
    LOG_TO_CONSOLE = True
    LOG_TO_FLASH   = True

_configured = False
_log_file_path = None
_root_logger = None


def _timestamp():
    try:
        t = time.localtime()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*t[:6])
    except Exception:
        return "0000-00-00 00:00:00"


class _FlushingFileHandler(logging.Handler):
    """Writes to a file and flushes after every record — MicroPython's
    stock FileHandler buffers and relies on close(), which a soft reboot
    or crash may never call."""

    def __init__(self, path, mode='a'):
        super().__init__()
        self._path = path
        self._mode = mode
        self._file = None
        self._open()

    def _open(self):
        try:
            self._file = open(self._path, self._mode)
        except Exception as e:
            print("logconfig: cannot open log file", self._path, e)
            self._file = None

    def emit(self, record):
        if self._file is None:
            return
        try:
            msg = self.format(record)
            self._file.write(msg + "\n")
            self._file.flush()
        except Exception as e:
            print("logconfig: write error", e)
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
            self._open()

    def flush(self):
        if self._file:
            try:
                self._file.flush()
            except Exception:
                pass

    def close(self):
        if self._file:
            try:
                self._file.flush()
                self._file.close()
            except Exception:
                pass
            self._file = None
        super().close()


class _FormattingHandler:
    """Namespace for the shared record format."""

    @staticmethod
    def format_record(record):
        try:
            ts   = _timestamp()
            name = record.name if hasattr(record, 'name') else 'root'
            lvl  = record.levelname if hasattr(record, 'levelname') else '?'
            msg  = record.getMessage() if hasattr(record, 'getMessage') else str(record.message)
            return "{} [{}] ({}) {}".format(ts, lvl, name, msg)
        except Exception:
            return str(record)


class _TimestampFileHandler(_FlushingFileHandler):
    """
    Rate-limited flushing: flush immediately on WARNING+, otherwise every
    _FLUSH_INTERVAL records or _FLUSH_MS after the oldest unflushed one.
    Internal flash has finite write endurance and each flush is a littlefs
    write — batching matters more here than on an SD card.
    """

    _FLUSH_INTERVAL = 20
    _FLUSH_MS       = 2000

    def __init__(self, path, mode='a'):
        super().__init__(path, mode)
        self._pending = 0
        self._last_flush = time.ticks_ms()

    def emit(self, record):
        if self._file is None:
            return
        try:
            msg = _FormattingHandler.format_record(record)
            self._file.write(msg + "\n")
            level = getattr(record, 'levelno', 0)
            now = time.ticks_ms()
            if (level >= 30
                    or self._pending >= self._FLUSH_INTERVAL
                    or (self._pending > 0
                        and time.ticks_diff(now, self._last_flush) >= self._FLUSH_MS)):
                self._file.flush()
                self._pending = 0
                self._last_flush = now
            else:
                self._pending += 1
        except Exception as e:
            print("logconfig: write error", e)
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
            self._pending = 0
            self._open()


class _TimestampStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = _FormattingHandler.format_record(record)
            self.stream.write(msg + "\n")
        except Exception as e:
            print("logconfig: stream error", e)


def _make_log_path():
    """Return a unique timestamped log file path under /syslog/."""
    try:
        os.mkdir("/syslog")
    except OSError:
        pass  # already exists

    try:
        t = time.localtime()
        fname = "log_{:04d}{:02d}{:02d}_{:02d}{:02d}{:02d}.log".format(*t[:6])
    except Exception:
        fname = "log_unknown.log"

    return "/syslog/" + fname


def configure(module_name: str) -> logging.Logger:
    """Configure the root logger. Call once from main.py before get_logger()."""
    global _configured, _log_file_path, _root_logger

    level = logging.WARNING if MODE == "production" else logging.DEBUG

    _log_file_path = _make_log_path() if LOG_TO_FLASH else None

    logger = logging.getLogger(module_name)
    logger.setLevel(level)
    logger.handlers = []   # idempotent reconfiguration

    if _log_file_path:
        fh = _TimestampFileHandler(_log_file_path, mode='a')
        fh.setLevel(level)
        logger.addHandler(fh)

    if LOG_TO_CONSOLE and MODE != "production":
        sh = _TimestampStreamHandler()
        sh.setLevel(level)
        logger.addHandler(sh)

    logger.info("Logging started. file=%s", _log_file_path)

    _configured = True
    _root_logger = logger
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a named child logger. configure() must have been called first."""
    if not _configured:
        raise RuntimeError("Logging not configured; call configure() first.")

    child = logging.getLogger(name)
    child.setLevel(_root_logger.level)
    if not child.handlers:
        child.handlers = _root_logger.handlers
    return child


async def _logrotate_task():
    """
    Periodically check flash usage and delete oldest syslog files if the
    filesystem is over 90% full. Started as an asyncio task from main.py.
    """
    import asyncio

    while True:
        await asyncio.sleep(60)
        try:
            stat = os.statvfs('/')
            total = stat[2]
            free  = stat[3]
            if total == 0:
                continue
            used_pct = (total - free) / total * 100
            if used_pct < 90:
                continue

            logs = sorted([f for f in os.listdir('/syslog') if f.endswith('.log')])
            for fname in logs:
                os.remove('/syslog/' + fname)
                stat = os.statvfs('/')
                free = stat[3]
                used_pct = (stat[2] - free) / stat[2] * 100
                if used_pct < 80:
                    break
        except Exception:
            pass
