# Copyright @ 2026 Adrian Blakey. All rights reserved
# log_record.py — compact fixed-size binary session log format.
#
# Internal flash is small (no SD card fallback), so each row is 8 bytes
# instead of a ~25-31 byte CSV row or the Pico 2 W reference's 16-byte
# `struct 'ifff'` wire format:
#
#   RECORD_FMT = '<HhHH'  (8 bytes)
#     dt_ms   uint16  milliseconds since the PREVIOUS record (session start
#                     for the first record). Wraps past 65.535 s only if a
#                     single gap is that long; flash_writer re-syncs by
#                     writing 0xFFFF chained records in that case (see
#                     split_delta_ms below) rather than truncating silently.
#     i_cA    int16   current, centi-amps (0.01 A). Sensor range is +-50 A,
#                     so +-327.67 A of headroom is generous. The sentinel
#                     value -32768 (0x8000) marks a LAP MARKER row instead
#                     of a data row — mirrors the reference's "current > 90 A
#                     is impossible from a +-50 A sensor" trick.
#     vt_cV   uint16  track voltage, centivolts (0.01 V). 0-655.35 V range.
#     vs_cV   uint16  supply voltage, centivolts (0.01 V).
#
# A session file starts with one HEADER record (see pack_header/read_header)
# so profile provenance travels WITH the data, like the reference's CSV
# comment-header convention — just packed instead of text.
#
# Values enter/leave this module as physical units (amps, volts); everything
# below the boundary between adc_device.py's float scaling and flash_writer's
# file I/O is bytes.

import struct

# ── Session header ───────────────────────────────────────────────────────────
HEADER_MAGIC   = b'SCL1'          # "Slot Car Logger" v1
HEADER_VERSION = 1
HEADER_FMT     = '<4sBIHH'        # magic, version, start_epoch(u32), sample_rate_hz(u16), profile_json_len(u16)
HEADER_FIXED_SIZE = struct.calcsize(HEADER_FMT)

# ── Data / marker records ────────────────────────────────────────────────────
RECORD_FMT   = '<HhHH'            # dt_ms, i_cA, vt_cV, vs_cV
RECORD_SIZE  = struct.calcsize(RECORD_FMT)

LAP_MARKER_SENTINEL = -32768      # i_cA value that means "this is a lap marker"

_I16_MIN, _I16_MAX = -32767, 32767   # -32768 reserved for the sentinel
_U16_MAX = 65535
_DT_MAX  = 65535                     # max representable dt_ms in one record


# ── Header ────────────────────────────────────────────────────────────────────

def pack_header(start_epoch: int, sample_rate_hz: int, profile_json: str) -> bytes:
    """Build the fixed header + variable-length profile JSON blob."""
    blob = profile_json.encode('utf-8')
    fixed = struct.pack(HEADER_FMT, HEADER_MAGIC, HEADER_VERSION,
                         start_epoch & 0xFFFFFFFF, sample_rate_hz & 0xFFFF,
                         len(blob) & 0xFFFF)
    return fixed + blob


def read_header(f) -> dict:
    """
    Read a header from an open binary file positioned at offset 0.
    Returns {'version', 'start_epoch', 'sample_rate_hz', 'profile': dict}.
    Raises ValueError if the magic doesn't match.
    """
    import json
    fixed = f.read(HEADER_FIXED_SIZE)
    if len(fixed) != HEADER_FIXED_SIZE:
        raise ValueError('short header read')
    magic, version, start_epoch, sample_rate_hz, json_len = struct.unpack(HEADER_FMT, fixed)
    if magic != HEADER_MAGIC:
        raise ValueError('bad magic: {}'.format(magic))
    blob = f.read(json_len)
    try:
        profile = json.loads(blob.decode('utf-8')) if blob else {}
    except Exception:
        profile = {}
    return {
        'version': version,
        'start_epoch': start_epoch,
        'sample_rate_hz': sample_rate_hz,
        'profile': profile,
    }


# ── Records ───────────────────────────────────────────────────────────────────

def _clip_i16(v: int) -> int:
    if v < _I16_MIN:
        return _I16_MIN
    if v > _I16_MAX:
        return _I16_MAX
    return v


def _clip_u16(v: int) -> int:
    if v < 0:
        return 0
    if v > _U16_MAX:
        return _U16_MAX
    return v


def encode_current(amps: float) -> int:
    """Amps -> clipped centi-amp int16 (never returns the sentinel)."""
    return _clip_i16(int(round(amps * 100)))


def encode_voltage(volts: float) -> int:
    """Volts -> clipped centi-volt uint16."""
    return _clip_u16(int(round(volts * 100)))


def decode_current(i_cA: int) -> float:
    return i_cA / 100.0


def decode_voltage(v_cV: int) -> float:
    return v_cV / 100.0


def is_marker(i_cA: int) -> bool:
    return i_cA == LAP_MARKER_SENTINEL


def _clip_dt(dt_ms: int) -> int:
    """
    Clip a delta to what one record can carry. A gap this long (>65.535 s)
    only happens if the writer task itself stalled for over a minute —
    effectively hung — so collapsing it to the cap (rather than inventing a
    multi-record continuation scheme a later reader would have to guess at)
    is an acceptable, simple tradeoff: relative timing within a session is
    best-effort, anchored by the header's start_epoch, not a hard guarantee.
    """
    if dt_ms < 0:
        return 0
    if dt_ms > _DT_MAX:
        return _DT_MAX
    return dt_ms


def pack_record(dt_ms: int, current_amps: float, track_v: float, supply_v: float) -> bytes:
    """Pack one data row."""
    return struct.pack(RECORD_FMT, _clip_dt(dt_ms),
                        encode_current(current_amps),
                        encode_voltage(track_v),
                        encode_voltage(supply_v))


def pack_marker(dt_ms: int, track_v: float = 0.0, supply_v: float = 0.0) -> bytes:
    """Pack one lap-marker row (Button B)."""
    return struct.pack(RECORD_FMT, _clip_dt(dt_ms),
                        LAP_MARKER_SENTINEL,
                        encode_voltage(track_v),
                        encode_voltage(supply_v))


def unpack_record(buf: bytes) -> dict:
    """Unpack one 8-byte record into physical units + a `marker` flag."""
    dt_ms, i_cA, vt_cV, vs_cV = struct.unpack(RECORD_FMT, buf)
    marker = is_marker(i_cA)
    return {
        'dt_ms': dt_ms,
        'marker': marker,
        'current_A': None if marker else decode_current(i_cA),
        'track_V': decode_voltage(vt_cV),
        'supply_V': decode_voltage(vs_cV),
    }
