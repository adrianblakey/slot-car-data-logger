# Copyright @ 2026 Adrian Blakey. All rights reserved
# Captures messages/errors before the log is initialized - used for sd and reset
import time

class ErrorBuffer:
    def __init__(self, size):
        self._size = size
        self._buf = [None] * size
        self._head = 0
        self._tail = 0
        self._full = False

    # ------------------------------------------------------------------
    def _now(self):
        try:
            t = time.localtime()
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*t[:6])
        except Exception:
            return str(time.time())

    # ------------------------------------------------------------------
    def record(self, msg):
        entry = "[{}] {}".format(self._now(), msg)

        self._buf[self._head] = entry
        self._head = (self._head + 1) % self._size

        if self._full:
            self._tail = (self._tail + 1) % self._size
        elif self._head == self._tail:
            self._full = True

    # ------------------------------------------------------------------
    def get_all(self, clear=True):
        """Return all entries oldest-first. If clear=True (default) reset the buffer."""
        out = []

        if (self._head == self._tail) and not self._full:
            return out

        # When full, read exactly _size entries starting from _tail (oldest).
        if self._full:
            count = self._size
            i = self._tail
            for _ in range(count):
                entry = self._buf[i]
                if entry is not None:
                    out.append(entry)
                i = (i + 1) % self._size
        else:
            i = self._tail
            while True:
                entry = self._buf[i]
                if entry is not None:
                    out.append(entry)
                if i == self._head:
                    break
                i = (i + 1) % self._size

        if clear:
            self._buf  = [None] * self._size
            self._head = 0
            self._tail = 0
            self._full = False

        return out

    # ------------------------------------------------------------------
    def clear(self):
        self._buf = [None] * self._size
        self._head = 0
        self._tail = 0
        self._full = False
