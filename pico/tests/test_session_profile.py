# Copyright @ 2026 Adrian Blakey. All rights reserved
# test_session_profile.py — host-side tests for the race session profile.
# session_profile.py has no hardware imports (json only), so this runs on
# plain CPython. _PATH is a hardcoded absolute path (unlike flash_writer's
# data_dir constructor arg), so tests monkeypatch session_profile._PATH to a
# temp file rather than touching the real /conf/profile.json.

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import session_profile as sp


class ProfileTestBase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(prefix='scl_profile_', suffix='.json')
        os.close(fd)
        os.remove(self.path)   # start with no file, like a fresh device
        self._orig_path = sp._PATH
        sp._PATH = self.path

    def tearDown(self):
        sp._PATH = self._orig_path
        if os.path.exists(self.path):
            os.remove(self.path)


class TestDefaultsAndPersistence(ProfileTestBase):
    def test_load_with_no_file_returns_defaults(self):
        p = sp.Profile.load()
        self.assertEqual(p.track, 'unknown')
        self.assertEqual(p.race, 'practice')
        self.assertEqual(p.lane, 1)
        self.assertEqual(p.controller, 'unknown')
        self.assertEqual(p.car, 'unknown')

    def test_save_then_load_round_trips(self):
        p = sp.Profile.load()
        p.update(track='Daytona', lane=3)
        p2 = sp.Profile.load()
        self.assertEqual(p2.track, 'Daytona')
        self.assertEqual(p2.lane, 3)

    def test_update_ignores_unknown_keys_and_none_values(self):
        p = sp.Profile.load()
        p.update(track='Daytona', bogus_field='x', lane=None)
        self.assertEqual(p.track, 'Daytona')
        self.assertFalse(hasattr(p, 'bogus_field'))
        self.assertEqual(p.lane, 1)   # untouched by the None

    def test_load_with_corrupt_json_falls_back_to_defaults(self):
        with open(self.path, 'w') as f:
            f.write('{not valid json')
        p = sp.Profile.load()
        self.assertEqual(p.lane, 1)


class TestLaneColor(unittest.TestCase):
    def test_lane_color_known(self):
        self.assertEqual(sp.lane_color(1), 'Black')
        self.assertEqual(sp.lane_color(8), 'Red')

    def test_lane_color_out_of_range(self):
        self.assertEqual(sp.lane_color(0), '?')
        self.assertEqual(sp.lane_color(9), '?')


class TestRotateLane(ProfileTestBase):
    def test_rotate_advances_by_one(self):
        p = sp.Profile.load()
        self.assertEqual(p.lane, 1)
        p.rotate_lane()
        self.assertEqual(p.lane, 2)

    def test_rotate_wraps_after_last_colour(self):
        p = sp.Profile.load()
        p.update(lane=len(sp.LANE_COLORS))
        p.rotate_lane()
        self.assertEqual(p.lane, 1)

    def test_rotate_persists(self):
        p = sp.Profile.load()
        p.rotate_lane()
        p2 = sp.Profile.load()
        self.assertEqual(p2.lane, 2)

    def test_rotate_recovers_from_invalid_stored_lane(self):
        # e.g. old on-disk data from before LANE_COLORS changed length.
        p = sp.Profile.load()
        p.lane = 99
        p.rotate_lane()
        self.assertTrue(1 <= p.lane <= len(sp.LANE_COLORS))


class TestToggleRace(ProfileTestBase):
    def test_toggle_from_practice_goes_to_race(self):
        p = sp.Profile.load()
        self.assertEqual(p.race, 'practice')
        p.toggle_race()
        self.assertEqual(p.race, 'race')

    def test_toggle_twice_returns_to_practice(self):
        p = sp.Profile.load()
        p.toggle_race()
        p.toggle_race()
        self.assertEqual(p.race, 'practice')

    def test_toggle_from_arbitrary_value_lands_on_race(self):
        p = sp.Profile.load()
        p.race = 'qualifying'
        p.toggle_race()
        self.assertEqual(p.race, 'race')

    def test_toggle_persists(self):
        p = sp.Profile.load()
        p.toggle_race()
        p2 = sp.Profile.load()
        self.assertEqual(p2.race, 'race')


if __name__ == '__main__':
    unittest.main()
