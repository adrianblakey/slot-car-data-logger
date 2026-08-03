# Copyright @ 2026 Adrian Blakey. All rights reserved
# session_profile.py — the race session profile.
#
# Profile tuple: (track, race, lane, controller, car).
# Persists in /conf/profile.json and survives reboot. Session start time is
# NOT stored here: it is stamped per session at the moment the binary log
# file is opened (see flash_writer.py).
#
# Adapted from the Pico 2 W reference (session_profile.py): same field set
# and JSON persistence, but no CSV comment-header method — flash_writer.py
# embeds the profile as a short JSON blob in the binary session header
# instead (see log_record.py: pack_header/unpack_header), since a fixed-width
# struct field would either truncate track/car names or waste space on every
# short one.

import json

_PATH = '/conf/profile.json'

# Conventional slot car lane colours, index = lane number - 1.
LANE_COLORS = ('Black', 'Purple', 'Yellow', 'Blue',
               'Orange', 'Green', 'White', 'Red')


def lane_color(lane):
    """Colour name for a 1-based lane number ('?' if out of range)."""
    return LANE_COLORS[lane - 1] if 1 <= lane <= len(LANE_COLORS) else '?'


_DEFAULTS = {
    'track':      'unknown',
    'race':       'practice',
    'lane':       1,
    'controller': 'unknown',
    'car':        'unknown',
}


class Profile:
    """Current session profile. Use the module-level PROFILE singleton."""

    def __init__(self, d=None):
        d = d or {}
        for k, v in _DEFAULTS.items():
            setattr(self, k, d.get(k, v))

    @classmethod
    def load(cls):
        try:
            with open(_PATH) as f:
                return cls(json.load(f))
        except Exception:
            return cls()    # no file / bad JSON -> defaults

    def save(self):
        try:
            with open(_PATH, 'w') as f:
                json.dump({k: getattr(self, k) for k in _DEFAULTS}, f)
            return True
        except Exception as e:
            print('session_profile: save failed:', e)
            return False

    def update(self, **kwargs):
        """Set any subset of fields (validated keys only) and persist."""
        for k in _DEFAULTS:
            if k in kwargs and kwargs[k] is not None:
                setattr(self, k, kwargs[k])
        return self.save()

    def as_dict(self):
        return {k: getattr(self, k) for k in _DEFAULTS}

    def as_json(self):
        """Compact JSON blob embedded in the binary session header."""
        return json.dumps(self.as_dict())

    def __repr__(self):
        return 'Profile({})'.format(self.as_dict())


PROFILE = Profile.load()
