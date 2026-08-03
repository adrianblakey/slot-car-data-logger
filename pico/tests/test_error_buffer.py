# Copyright @ 2026 Adrian Blakey. All rights reserved
# test_error_buffer.py — error_buffer.py is reused verbatim from the
# Pico 2 W reference (no hardware imports), so this test is too.

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import mocks  # noqa: F401 — must be first

import unittest
from error_buffer import ErrorBuffer


class TestErrorBuffer(unittest.TestCase):

    def test_empty_on_creation(self):
        buf = ErrorBuffer(8)
        self.assertEqual(buf.get_all(), [])

    def test_record_and_retrieve(self):
        buf = ErrorBuffer(8)
        buf.record("first")
        buf.record("second")
        items = buf.get_all()
        self.assertEqual(len(items), 2)
        self.assertIn("first", items[0])
        self.assertIn("second", items[1])

    def test_get_all_clears_by_default(self):
        buf = ErrorBuffer(4)
        buf.record("msg")
        buf.get_all(clear=True)
        self.assertEqual(buf.get_all(), [])

    def test_get_all_no_clear(self):
        buf = ErrorBuffer(4)
        buf.record("msg")
        buf.get_all(clear=False)
        self.assertNotEqual(buf.get_all(), [])

    def test_circular_overflow_keeps_newest(self):
        buf = ErrorBuffer(4)
        for i in range(6):
            buf.record("msg{}".format(i))
        items = buf.get_all()
        self.assertLessEqual(len(items), 4)
        text = " ".join(items)
        self.assertIn("msg5", text)
        self.assertIn("msg4", text)

    def test_timestamp_in_record(self):
        buf = ErrorBuffer(4)
        buf.record("hello")
        items = buf.get_all(clear=False)
        self.assertTrue(any('[' in item for item in items))

    def test_multiple_buffers_independent(self):
        a = ErrorBuffer(4)
        b = ErrorBuffer(4)
        a.record("in-a")
        b.record("in-b")
        self.assertIn("in-a", " ".join(a.get_all()))
        self.assertIn("in-b", " ".join(b.get_all()))
        self.assertNotIn("in-a", " ".join(b.get_all()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
