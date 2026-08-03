# Copyright @ 2026 Adrian Blakey. All rights reserved
# test_log_record.py — host-side tests for the compact binary log format.
# No hardware imports in log_record.py, so this runs on plain CPython.

import io
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import log_record as lr


class TestRecordSize(unittest.TestCase):
    def test_record_is_8_bytes(self):
        self.assertEqual(lr.RECORD_SIZE, 8)


class TestRecordRoundTrip(unittest.TestCase):
    def test_pack_unpack_typical_values(self):
        packed = lr.pack_record(5, 12.34, 11.98, 12.05)
        self.assertEqual(len(packed), 8)
        row = lr.unpack_record(packed)
        self.assertEqual(row['dt_ms'], 5)
        self.assertFalse(row['marker'])
        self.assertAlmostEqual(row['current_A'], 12.34, places=2)
        self.assertAlmostEqual(row['track_V'], 11.98, places=2)
        self.assertAlmostEqual(row['supply_V'], 12.05, places=2)

    def test_negative_current_braking(self):
        packed = lr.pack_record(1, -3.5, 12.0, 12.0)
        row = lr.unpack_record(packed)
        self.assertAlmostEqual(row['current_A'], -3.5, places=2)

    def test_zero_dt(self):
        packed = lr.pack_record(0, 0.0, 0.0, 0.0)
        row = lr.unpack_record(packed)
        self.assertEqual(row['dt_ms'], 0)

    def test_max_dt_ms(self):
        packed = lr.pack_record(65535, 1.0, 1.0, 1.0)
        row = lr.unpack_record(packed)
        self.assertEqual(row['dt_ms'], 65535)


class TestClipping(unittest.TestCase):
    def test_current_clips_below_range_without_hitting_sentinel(self):
        packed = lr.pack_record(0, -400.0, 0.0, 0.0)
        row = lr.unpack_record(packed)
        # Clipped to _I16_MIN (-32767 centi-amps), not the -32768 sentinel.
        self.assertFalse(row['marker'])
        self.assertAlmostEqual(row['current_A'], -327.67, places=2)

    def test_current_clips_above_range(self):
        packed = lr.pack_record(0, 400.0, 0.0, 0.0)
        row = lr.unpack_record(packed)
        self.assertAlmostEqual(row['current_A'], 327.67, places=2)

    def test_voltage_never_negative(self):
        self.assertEqual(lr.encode_voltage(-5.0), 0)

    def test_voltage_clips_above_range(self):
        self.assertEqual(lr.encode_voltage(700.0), lr._U16_MAX)


class TestLapMarker(unittest.TestCase):
    def test_marker_round_trip(self):
        packed = lr.pack_marker(12, track_v=11.9, supply_v=12.1)
        row = lr.unpack_record(packed)
        self.assertTrue(row['marker'])
        self.assertIsNone(row['current_A'])
        self.assertAlmostEqual(row['track_V'], 11.9, places=2)

    def test_sentinel_is_unreachable_from_real_current(self):
        # Even at the most extreme clip, encode_current never produces the
        # sentinel value -32768.
        self.assertNotEqual(lr.encode_current(-1e9), lr.LAP_MARKER_SENTINEL)
        self.assertNotEqual(lr.encode_current(1e9), lr.LAP_MARKER_SENTINEL)

    def test_is_marker_helper(self):
        self.assertTrue(lr.is_marker(lr.LAP_MARKER_SENTINEL))
        self.assertFalse(lr.is_marker(0))
        self.assertFalse(lr.is_marker(-32767))


class TestDeltaClipping(unittest.TestCase):
    def test_typical_delta_unclipped(self):
        row = lr.unpack_record(lr.pack_record(5, 1.0, 12.0, 12.0))
        self.assertEqual(row['dt_ms'], 5)

    def test_delta_at_cap_unclipped(self):
        row = lr.unpack_record(lr.pack_record(65535, 1.0, 12.0, 12.0))
        self.assertEqual(row['dt_ms'], 65535)

    def test_delta_beyond_cap_is_clipped(self):
        row = lr.unpack_record(lr.pack_record(200_000, 1.0, 12.0, 12.0))
        self.assertEqual(row['dt_ms'], 65535)

    def test_negative_delta_clips_to_zero(self):
        row = lr.unpack_record(lr.pack_record(-5, 1.0, 12.0, 12.0))
        self.assertEqual(row['dt_ms'], 0)


class TestHeader(unittest.TestCase):
    def test_header_round_trip(self):
        profile_json = '{"track": "Castle", "lane": 4}'
        blob = lr.pack_header(1_700_000_000, 200, profile_json)
        f = io.BytesIO(blob)
        hdr = lr.read_header(f)
        self.assertEqual(hdr['version'], lr.HEADER_VERSION)
        self.assertEqual(hdr['start_epoch'], 1_700_000_000)
        self.assertEqual(hdr['sample_rate_hz'], 200)
        self.assertEqual(hdr['profile'], {'track': 'Castle', 'lane': 4})

    def test_header_then_records_stream(self):
        blob = lr.pack_header(0, 200, '{}')
        blob += lr.pack_record(5, 1.0, 12.0, 12.0)
        blob += lr.pack_marker(5)
        f = io.BytesIO(blob)
        hdr = lr.read_header(f)
        self.assertEqual(hdr['profile'], {})
        row1 = lr.unpack_record(f.read(lr.RECORD_SIZE))
        self.assertFalse(row1['marker'])
        row2 = lr.unpack_record(f.read(lr.RECORD_SIZE))
        self.assertTrue(row2['marker'])

    def test_bad_magic_raises(self):
        f = io.BytesIO(b'\x00' * lr.HEADER_FIXED_SIZE)
        with self.assertRaises(ValueError):
            lr.read_header(f)


if __name__ == '__main__':
    unittest.main()
