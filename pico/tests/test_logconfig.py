# Copyright @ 2026 Adrian Blakey. All rights reserved
# test_logconfig.py — logconfig.py is flash-only (no SD branch to test,
# unlike the reference), so this is simpler than its Pico 2 W counterpart.

import sys
import os
import logging
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import mocks  # noqa: F401 — must be first


class TestLogconfig(unittest.TestCase):

    def setUp(self):
        for mod in list(sys.modules):
            if mod == 'logconfig':
                del sys.modules[mod]

    def _patches(self):
        return (
            mock.patch('os.mkdir', return_value=None),
            mock.patch('builtins.open', mock.mock_open()),
        )

    def test_configure_returns_logger(self):
        p1, p2 = self._patches()
        with p1, p2:
            import logconfig
            logger = logconfig.configure("test")
        self.assertIsNotNone(logger)

    def test_get_logger_after_configure(self):
        p1, p2 = self._patches()
        with p1, p2:
            import logconfig
            logconfig.configure("test")
            child = logconfig.get_logger("child_module")
        self.assertIsNotNone(child)
        self.assertIs(child.handlers, logconfig._root_logger.handlers)

    def test_get_logger_before_configure_raises(self):
        import logconfig
        with self.assertRaises(RuntimeError):
            logconfig.get_logger("premature")

    def test_log_file_opened_under_syslog(self):
        p1, p2 = self._patches()
        with p1, p2 as m:
            import logconfig
            logconfig.configure("test")
        calls = [str(c) for c in m.call_args_list]
        self.assertTrue(any('/syslog' in c for c in calls),
                         msg="Expected a file opened under /syslog, got: {}".format(calls))

    def test_debug_mode_has_stream_handler(self):
        p1, p2 = self._patches()
        with p1, p2:
            import logconfig
            logger = logconfig.configure("test")
        self.assertTrue(
            any(isinstance(h, logging.StreamHandler) for h in logger.handlers),
            msg="Expected a StreamHandler in debug mode, got: {}".format(
                [type(h).__name__ for h in logger.handlers]))

    def test_production_mode_has_no_stream_handler(self):
        p1, p2 = self._patches()
        with p1, p2:
            import logconfig
            logconfig.MODE = "production"
            try:
                logger = logconfig.configure("test")
            finally:
                logconfig.MODE = "debug"
        self.assertFalse(
            any(isinstance(h, logging.StreamHandler) for h in logger.handlers),
            msg="Did not expect a StreamHandler in production mode")

    def test_reconfigure_is_idempotent(self):
        p1, p2 = self._patches()
        with p1, p2:
            import logconfig
            logconfig.configure("test")
            n_handlers_first = len(logconfig._root_logger.handlers)
            logconfig.configure("test")
            n_handlers_second = len(logconfig._root_logger.handlers)
        self.assertEqual(n_handlers_first, n_handlers_second)


if __name__ == '__main__':
    unittest.main(verbosity=2)
