# Copyright @ 2026 Adrian Blakey. All rights reserved
# test_flash_writer.py — host-side tests for session lifecycle + quota guard.
# flash_writer.py has no hardware imports (os/time/json only), so this runs
# on plain CPython against a real temp directory.

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import flash_writer as fw
import log_record as lr


class FlashWriterTestBase(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp(prefix='scl_test_')

    def tearDown(self):
        shutil.rmtree(self.data_dir, ignore_errors=True)


class TestSessionLifecycle(FlashWriterTestBase):
    def test_start_creates_file_with_header(self):
        w = fw.FlashWriter(data_dir=self.data_dir, sample_rate_hz=200)
        fname = w.start(start_epoch=1_700_000_000)
        self.assertTrue(w.is_open())
        self.assertTrue(os.path.exists(fname))
        w.close()
        self.assertFalse(w.is_open())

        with open(fname, 'rb') as f:
            hdr = lr.read_header(f)
        self.assertEqual(hdr['start_epoch'], 1_700_000_000)
        self.assertEqual(hdr['sample_rate_hz'], 200)

    def test_write_sample_then_marker_round_trips(self):
        w = fw.FlashWriter(data_dir=self.data_dir)
        fname = w.start(start_epoch=0)
        w.write_sample(0, 1.0, 12.0, 12.0)
        w.write_sample(5000, 1.5, 12.0, 12.0)     # +5 ms
        w.write_marker(10000)                      # +5 ms
        self.assertEqual(w.record_count(), 3)
        w.close()

        with open(fname, 'rb') as f:
            lr.read_header(f)
            r1 = lr.unpack_record(f.read(lr.RECORD_SIZE))
            r2 = lr.unpack_record(f.read(lr.RECORD_SIZE))
            r3 = lr.unpack_record(f.read(lr.RECORD_SIZE))
        self.assertEqual(r1['dt_ms'], 0)
        self.assertEqual(r2['dt_ms'], 5)
        self.assertEqual(r3['dt_ms'], 5)
        self.assertFalse(r1['marker'])
        self.assertTrue(r3['marker'])

    def test_cannot_start_twice(self):
        w = fw.FlashWriter(data_dir=self.data_dir)
        w.start()
        with self.assertRaises(RuntimeError):
            w.start()
        w.close()

    def test_write_before_start_is_a_noop(self):
        w = fw.FlashWriter(data_dir=self.data_dir)
        w.write_sample(0, 1.0, 12.0, 12.0)   # no file open — must not raise
        self.assertEqual(w.record_count(), 0)

    def test_new_session_after_close(self):
        w = fw.FlashWriter(data_dir=self.data_dir)
        f1 = w.start(start_epoch=100)
        w.close()
        f2 = w.start(start_epoch=200)
        w.close()
        self.assertNotEqual(f1, f2)
        self.assertEqual(len(fw.list_sessions(self.data_dir)), 2)


class TestSessionListingAndErase(FlashWriterTestBase):
    def test_list_sessions_sorted_and_filtered(self):
        fw.ensure_data_dir(self.data_dir)
        open(os.path.join(self.data_dir, 'session_b.bin'), 'w').close()
        open(os.path.join(self.data_dir, 'session_a.bin'), 'w').close()
        open(os.path.join(self.data_dir, 'not_a_session.txt'), 'w').close()
        self.assertEqual(fw.list_sessions(self.data_dir),
                          ['session_a.bin', 'session_b.bin'])

    def test_erase_all_removes_only_sessions(self):
        fw.ensure_data_dir(self.data_dir)
        open(os.path.join(self.data_dir, 'session_a.bin'), 'w').close()
        open(os.path.join(self.data_dir, 'keep.txt'), 'w').close()
        n = fw.erase_all(self.data_dir)
        self.assertEqual(n, 1)
        self.assertIn('keep.txt', os.listdir(self.data_dir))
        self.assertEqual(fw.list_sessions(self.data_dir), [])


class TestQuotaGuard(FlashWriterTestBase):
    def setUp(self):
        super().setUp()
        self._orig_free_bytes = fw._free_bytes
        self._orig_auto_rotate = fw.FLASH_AUTO_ROTATE

    def tearDown(self):
        fw._free_bytes = self._orig_free_bytes
        fw.FLASH_AUTO_ROTATE = self._orig_auto_rotate
        super().tearDown()

    def test_quota_state_ok(self):
        fw._free_bytes = lambda path='/': fw.FLASH_LOW_WARN + 1
        self.assertEqual(fw.FlashWriter.quota_state(), 'ok')

    def test_quota_state_low(self):
        fw._free_bytes = lambda path='/': fw.FLASH_MIN_FREE + 1
        self.assertEqual(fw.FlashWriter.quota_state(), 'low')

    def test_quota_state_full(self):
        fw._free_bytes = lambda path='/': fw.FLASH_MIN_FREE - 1
        self.assertEqual(fw.FlashWriter.quota_state(), 'full')

    def test_start_raises_when_full_and_rotate_disabled(self):
        fw.FLASH_AUTO_ROTATE = False
        fw._free_bytes = lambda path='/': 0
        w = fw.FlashWriter(data_dir=self.data_dir)
        with self.assertRaises(fw.FlashQuotaError):
            w.start()
        self.assertFalse(w.is_open())

    def test_start_rotates_oldest_when_full_and_rotate_enabled(self):
        # Seed one existing session so there's something to rotate away.
        fw.ensure_data_dir(self.data_dir)
        old_path = os.path.join(self.data_dir, 'session_00000000_000000.bin')
        open(old_path, 'w').close()

        fw.FLASH_AUTO_ROTATE = True
        calls = {'n': 0}

        def fake_free_bytes(path='/'):
            calls['n'] += 1
            # First check: full (triggers rotation). After rotation: ok.
            return 0 if calls['n'] == 1 else fw.FLASH_LOW_WARN + 1

        fw._free_bytes = fake_free_bytes
        w = fw.FlashWriter(data_dir=self.data_dir)
        w.start(start_epoch=999)
        self.assertTrue(w.is_open())
        self.assertFalse(os.path.exists(old_path))   # rotated away
        w.close()

    def test_start_still_raises_when_rotation_cant_free_enough(self):
        fw.FLASH_AUTO_ROTATE = True
        fw._free_bytes = lambda path='/': 0   # always full, nothing to rotate
        w = fw.FlashWriter(data_dir=self.data_dir)
        with self.assertRaises(fw.FlashQuotaError):
            w.start()


if __name__ == '__main__':
    unittest.main()
