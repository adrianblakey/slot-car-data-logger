# Copyright @ 2026 Adrian Blakey. All rights reserved
# ble_server.py — aioble GATT server: device info + logger status/control.
#
# Consolidates and wires up the early prototype's bt_server.py plus its
# several "not used yet" bt_service*.py duplicates into one working service
# set. Keeps its neat trick of folding the current IP address into the
# Device Information "Firmware Revision" characteristic, so a phone paired
# over BLE (but not necessarily on the same Wi-Fi) can still discover the IP
# to open the web UI.
#
# main.py owns the real state (recording flag, flash usage, record count,
# button handlers); this module never imports main, it's wired up via
# configure(status_fn, control_fn, ip_getter) instead — same pattern
# buzzer/fatal_handler use for the same reason.

import sys
import os
import io
import struct
import asyncio
import aioble
import bluetooth
import machine

from session_profile import PROFILE
import flash_writer as fw
import logconfig

try:
    from CONFIG import BLE_FILE_CHUNK_SIZE
except Exception:
    BLE_FILE_CHUNK_SIZE = 180

log = None


def _log():
    global log
    if log is None:
        log = logconfig.get_logger("ble")
    return log


_ADV_INTERVAL_MS = 250_000

# Device Information service (standard org.bluetooth.service.device_information).
_DEVICE_SVC_UUID    = bluetooth.UUID(0x180A)
_DEVICE_MFG_UUID    = bluetooth.UUID(0x2A29)
_DEVICE_SER_UUID    = bluetooth.UUID(0x2A25)
_DEVICE_FW_REV_UUID = bluetooth.UUID(0x2A26)   # carries "<ip> <sys.version>"
_DEVICE_SW_REV_UUID = bluetooth.UUID(0x2A28)

# Logger service (custom, vendor-specific UUIDs).
_LOGGER_SVC_UUID     = bluetooth.UUID('B1190EFA-176F-4B32-A715-89B3425A4076')
_LOGGER_STATUS_UUID  = bluetooth.UUID('B1190EFB-176F-4B32-A715-89B3425A4076')  # notify
_LOGGER_CONTROL_UUID = bluetooth.UUID('B1190EFC-176F-4B32-A715-89B3425A4076')  # write
_LOGGER_PROFILE_UUID = bluetooth.UUID('B1190EFD-176F-4B32-A715-89B3425A4076')  # read/write/notify

# Files service (custom, vendor-specific UUIDs) — download session data
# (.bin) and syslog (.log) files over BLE, and list what's available, all
# through just two characteristics. See README's "BLE file transfer" for
# the wire protocol; short version: write a short control code to
# FILE_SELECT (see _CTRL_* below — selecting a specific file is by its
# INDEX in the most recently fetched listing, not by name), then read (or
# wait for a notify on) FILE_CHUNK; empty = EOF.
#
# Two characteristics, not three or four, on purpose — confirmed on
# hardware that a third one silently failed to register at all (GATT
# discovery from a real central showed only 2 of the 3 characteristics
# this service defined; the Logger service's 3 registered fine, so this
# looks like a total-attribute-count ceiling on this MicroPython BLE
# build, not a per-service limit). Also deliberately no separate
# cached-JSON "list" characteristic even before hitting that ceiling — a
# single GATT attribute value is capped at 512 bytes by the BLE spec,
# which a flat file listing blows past once there are more than a handful
# of files on the device; confirmed on hardware too, a 7-file listing
# (~550 bytes of JSON) truncated mid-value and failed to parse on the
# central. Routing both "list" and "advance" through FILE_SELECT, and the
# listing itself through the same chunked path as real files, fixes both
# at once.
#
# Selection is by index, not filename, for a third reason found on
# hardware: real filenames (session_*.bin is 27 characters, log_*.log is
# 23) don't reliably fit in a single BLE write. The guaranteed-minimum
# ATT_MTU is 23 bytes (20 usable payload bytes after the 3-byte header),
# and a real BLE central (bleak, default settings) stayed there even
# after the device proactively requested a larger one on connect
# (connection.exchange_mtu() sent without error, but a real central
# simply didn't honour it) — the write silently landed truncated
# ("log_20210101_000003." — missing ".log") instead of raising an error,
# since MicroPython's bluetooth stack doesn't implement the GATT "queued
# write" fallback for oversized single writes either. A 3-byte
# select-by-index payload sidesteps needing MTU negotiation to work at
# all, which is more robust than trying to fix the negotiation.
_FILES_SVC_UUID    = bluetooth.UUID('B1190F00-176F-4B32-A715-89B3425A4076')
_FILE_SELECT_UUID  = bluetooth.UUID('B1190F02-176F-4B32-A715-89B3425A4076')  # write: control code, see _CTRL_*
_FILE_CHUNK_UUID   = bluetooth.UUID('B1190F03-176F-4B32-A715-89B3425A4076')  # read/notify: bytes, empty=EOF

# FILE_SELECT payloads:
#   _CTRL_NEXT (1 byte)         -> advance to the next chunk of the
#                                  current transfer
#   _CTRL_LIST (1 byte)         -> (re)start streaming the file listing
#                                  (JSON) instead of a specific file
#   _CTRL_SELECT + u16-LE index (3 bytes total) -> open the file at that
#                                  0-based position in the most recently
#                                  fetched listing's order (data files
#                                  first, then log files, each sorted —
#                                  see _file_entries)
_CTRL_NEXT   = b'\x00'
_CTRL_LIST   = b'\x01'
_CTRL_SELECT = 0x02

_ADV_APPEARANCE_LOGGER = 128   # org.bluetooth.characteristic.gap.appearance "Generic Computer"

# Control command bytes written by a central. Most are a single byte;
# CMD_LANE_SET takes a second payload byte (1-based lane number). See
# main.py's _ble_control_fn for the dispatch and README's "Abbreviated UI"
# for the full command table.
CMD_STOP        = 0
CMD_START       = 1
CMD_MARK        = 2
CMD_ERASE       = 3   # only takes effect if not currently recording; clears
                       # both session data and syslog files (see main.py's
                       # _do_erase) — download first if you want to keep them
CMD_WIFI_START  = 4   # gated by a free-heap check — see CONFIG.WIFI_MIN_FREE_BYTES
CMD_WIFI_STOP   = 5
CMD_LANE_ROTATE = 6
CMD_LANE_SET    = 7   # byte 1: lane number, 1-8
CMD_RACE_TOGGLE = 8   # flips practice <-> race

_STATUS_FMT = '<BBHB'  # recording(0/1), flash_free_pct(0-100), record_count(u16, wraps), wifi_up(0/1)


def _device_id() -> str:
    import ubinascii
    return ubinascii.hexlify(machine.unique_id()).decode()


class BLEServer:
    """
    Construct once in main.py, call configure() to wire it to live state,
    then run it as a background task: asyncio.create_task(server.run()).
    """

    def __init__(self):
        self._device_id = _device_id()
        self._status_fn  = None    # () -> dict(recording, flash_free_pct, record_count)
        self._control_fn = None    # (cmd:int) -> None
        self._ip_getter  = None    # () -> str or None
        self._on_connect = None    # () -> None, called on each new central connection
        self._connection = None

        # Currently-open file transfer, if any — see _file_select_task/
        # _prepare_chunk. One at a time: there's only one BLE connection
        # at once anyway (a single peripheral advertisement), so this
        # doesn't need to be keyed by connection.
        self._xfer_file = None
        self._xfer_name = None

        self._device_svc = aioble.Service(_DEVICE_SVC_UUID)
        self._mfg = aioble.Characteristic(
            self._device_svc, _DEVICE_MFG_UUID, read=True,
            initial=b"Adrian's And Richard's Technologies (AART)")
        self._ser = aioble.Characteristic(
            self._device_svc, _DEVICE_SER_UUID, read=True,
            initial=self._device_id.encode())
        self._fw = aioble.Characteristic(
            self._device_svc, _DEVICE_FW_REV_UUID, read=True,
            initial=sys.version.encode())
        self._sw = aioble.Characteristic(
            self._device_svc, _DEVICE_SW_REV_UUID, read=True,
            initial=b"Slot Car Logger (Pico W); v1")

        self._logger_svc = aioble.Service(_LOGGER_SVC_UUID)
        self._status = aioble.Characteristic(
            self._logger_svc, _LOGGER_STATUS_UUID, read=True, notify=True,
            initial=struct.pack(_STATUS_FMT, 0, 100, 0))
        self._control = aioble.Characteristic(
            self._logger_svc, _LOGGER_CONTROL_UUID, write=True, capture=True)
        self._profile = aioble.Characteristic(
            self._logger_svc, _LOGGER_PROFILE_UUID, read=True, write=True,
            notify=True, capture=True, initial=PROFILE.as_json().encode())

        self._files_svc = aioble.Service(_FILES_SVC_UUID)
        self._file_select = aioble.Characteristic(
            self._files_svc, _FILE_SELECT_UUID, write=True, capture=True)
        self._file_chunk = aioble.Characteristic(
            self._files_svc, _FILE_CHUNK_UUID, read=True, notify=True,
            initial=b'')

        aioble.register_services(self._device_svc, self._logger_svc, self._files_svc)

    def configure(self, status_fn, control_fn, ip_getter=None, on_connect=None) -> None:
        self._status_fn = status_fn
        self._control_fn = control_fn
        self._ip_getter = ip_getter
        self._on_connect = on_connect   # () -> None, called on each new central connection

    # ── advertise / connection lifecycle ──────────────────────────────────────

    def _refresh_fw_rev(self) -> None:
        ip = self._ip_getter() if self._ip_getter else None
        rev = "{} {}".format(ip or '-', sys.version)
        try:
            self._fw.write(rev.encode())
        except Exception:
            pass

    async def _peripheral_task(self):
        while True:
            # Advertised services are just a pre-connection discovery aid —
            # a connected central still finds Files via normal GATT service
            # discovery regardless of what's listed here. Deliberately NOT
            # including _FILES_SVC_UUID: BLE's legacy advertising payload
            # is capped at 31 bytes total, and each 128-bit custom UUID
            # costs 16 of them — two (logger + files) already blows the
            # budget once the device name and other AD structures are
            # added. Confirmed on hardware: the BLE task crashed at boot
            # with "ValueError: Advertising payload too long" the moment a
            # second 128-bit UUID was added here.
            async with await aioble.advertise(
                _ADV_INTERVAL_MS,
                name="SCLogger-" + self._device_id[0:6],
                services=[_DEVICE_SVC_UUID, _LOGGER_SVC_UUID],
                appearance=_ADV_APPEARANCE_LOGGER,
            ) as connection:
                _log().info("BLE connection from %s", connection.device)
                self._connection = connection
                # Ask for a larger MTU — doesn't call this a fix for
                # anything specific: confirmed on hardware that a real BLE
                # central (bleak, BlueZ backend) stayed at the bare
                # BLE-spec minimum (23) even after this request, which is
                # exactly why file selection below is index-based rather
                # than by filename (see the Files service comment). Kept
                # anyway on the general "helps throughput, can't hurt"
                # principle for status/profile notifications, in case a
                # different central does honour it.
                try:
                    await connection.exchange_mtu(247)
                except Exception as e:
                    _log().warning("BLE MTU exchange failed: %s", e)
                if self._on_connect is not None:
                    try:
                        self._on_connect()
                    except Exception:
                        pass
                while connection.is_connected():
                    await asyncio.sleep_ms(2000)
                self._connection = None
                self._close_xfer()   # release any file handle left open mid-transfer

    # ── status notify ────────────────────────────────────────────────────────

    async def _status_task(self):
        while True:
            if self._connection is not None and self._status_fn is not None:
                try:
                    st = self._status_fn()
                    packed = struct.pack(
                        _STATUS_FMT,
                        1 if st.get('recording') else 0,
                        max(0, min(100, st.get('flash_free_pct', 0))),
                        st.get('record_count', 0) & 0xFFFF,
                        1 if st.get('wifi_up') else 0)
                    self._status.write(packed)
                    self._status.notify(self._connection)
                except Exception as e:
                    _log().warning("BLE status notify failed: %s", e)
            await asyncio.sleep_ms(2000)

    # ── control write (start/stop/mark) ────────────────────────────────────────

    async def _control_task(self):
        while True:
            connection, data = await self._control.written()
            if not data:
                continue
            cmd = data[0]
            _log().info("BLE control received: %d", cmd)
            if self._control_fn is not None:
                try:
                    # Pass the whole payload, not just data[0]: CMD_LANE_SET
                    # needs a second byte (the lane number) that a bare cmd
                    # int would drop.
                    self._control_fn(cmd, data)
                except Exception as e:
                    _log().warning("BLE control handler failed: %s", e)

    # ── profile read/write ──────────────────────────────────────────────────

    def refresh_profile(self) -> None:
        """Push the current PROFILE out to the profile characteristic and
        notify. Needed because main.py's lane/race control commands
        (CMD_LANE_ROTATE/CMD_LANE_SET/CMD_RACE_TOGGLE) mutate PROFILE
        directly rather than by writing JSON to this characteristic, so
        _profile_task below never sees them — without this, a central
        reading the profile characteristic after one of those commands
        would see stale data."""
        try:
            self._profile.write(PROFILE.as_json().encode())
            if self._connection is not None:
                self._profile.notify(self._connection)
        except Exception as e:
            _log().warning("BLE profile refresh failed: %s", e)

    async def _profile_task(self):
        import json
        while True:
            connection, data = await self._profile.written()
            try:
                d = json.loads(data.decode())
                PROFILE.update(**d)
                self._profile.write(PROFILE.as_json().encode())
                self._profile.notify(connection)
                _log().info("Profile updated over BLE: %s", d)
            except Exception as e:
                _log().warning("Bad BLE profile write: %s", e)

    # ── file download ─────────────────────────────────────────────────────
    #
    # Wire protocol (see README's "BLE file transfer" for the full writeup):
    #   1. Write _CTRL_LIST to FILE_SELECT.
    #   2. Read (or wait for a notify on) FILE_CHUNK; write _CTRL_NEXT to
    #      FILE_SELECT and repeat until a chunk comes back empty. What
    #      you've reassembled is JSON: a list of {"name", "kind"
    #      ("data"/"log"), "size"} objects, in a fixed order (data files
    #      first, then log files, each sorted).
    #   3. To fetch one of them, write _CTRL_SELECT + its position in that
    #      list as a u16-LE (3 bytes total) to FILE_SELECT, then repeat
    #      step 2 to pull its contents. Empty on the very first read means
    #      the index was out of range (e.g. the list changed underneath
    #      you — erase or a new session — since step 2; re-fetch it).
    #
    # Like status/profile, FILE_CHUNK is a plain cached characteristic —
    # aioble's Characteristic serves whatever was last .write()-ten, it
    # doesn't compute a value live on read. So "read the next chunk" is
    # really "trigger prepare, then read (or get notified of) the cache."
    #
    # PACING REQUIREMENT, found on hardware: writing _CTRL_NEXT and
    # immediately reading FILE_CHUNK back-to-back in a tight loop (no
    # delay) intermittently corrupted the download — not dropped/duplicate
    # chunks, but a read landing mid-update and returning a splice of the
    # old and new chunk content (a torn read of _file_chunk's buffer,
    # racing this task's write against the read the BLE stack is actively
    # serving). Confirmed reproducible at ~20ms between write and read on
    # a 65 KB file, and confirmed CLEAN at ~150ms on the same file and
    # device state. Wait at least 100ms after writing _CTRL_NEXT (or
    # _CTRL_LIST/_CTRL_SELECT) before reading FILE_CHUNK.

    def _file_entries(self):
        """Ordered (path, name, kind, size) tuples — the single source of
        truth for both the JSON listing (_build_file_list) and
        select-by-index (_file_select_task), so the two always agree on
        what index N means. list_sessions()/list_logs() are both already
        sorted, so this order is stable as long as the underlying files
        haven't changed between a listing and a later select."""
        entries = []
        for data_dir, kind in ((fw.DATA_DIR, 'data'), (logconfig.LOG_DIR, 'log')):
            names = fw.list_sessions() if kind == 'data' else logconfig.list_logs()
            for name in names:
                path = data_dir + '/' + name
                try:
                    size = os.stat(path)[6]
                except OSError:
                    size = 0
                entries.append((path, name, kind, size))
        return entries

    def _build_file_list(self) -> bytes:
        import json
        return json.dumps([
            {'name': name, 'kind': kind, 'size': size}
            for _path, name, kind, size in self._file_entries()
        ]).encode()

    def _close_xfer(self) -> None:
        if self._xfer_file is not None:
            try:
                self._xfer_file.close()
            except Exception:
                pass
        self._xfer_file = None
        self._xfer_name = None

    def _prepare_chunk(self) -> None:
        """Read the next CONFIG.BLE_FILE_CHUNK_SIZE bytes from the open
        transfer (if any — a real file or an in-memory io.BytesIO, both
        support the same read(n) call) into the chunk characteristic. An
        empty chunk — nothing open, or exhausted — is the central's EOF
        signal; closes the transfer the moment that happens so a stray
        extra _CTRL_NEXT write afterwards is a harmless no-op."""
        if self._xfer_file is None:
            chunk = b''
        else:
            chunk = self._xfer_file.read(BLE_FILE_CHUNK_SIZE)
            if not chunk:
                self._close_xfer()
        try:
            self._file_chunk.write(chunk)
            if self._connection is not None:
                self._file_chunk.notify(self._connection)
        except Exception as e:
            _log().warning("BLE file chunk prepare failed: %s", e)

    async def _file_select_task(self):
        while True:
            connection, data = await self._file_select.written()
            if not data or data == _CTRL_NEXT:
                self._prepare_chunk()
                continue
            if data == _CTRL_LIST:
                self._close_xfer()
                self._xfer_file = io.BytesIO(self._build_file_list())
                self._prepare_chunk()
                continue
            if len(data) == 3 and data[0] == _CTRL_SELECT:
                index = data[1] | (data[2] << 8)
                self._close_xfer()
                entries = self._file_entries()
                if 0 <= index < len(entries):
                    path, name, _kind, _size = entries[index]
                    try:
                        self._xfer_file = open(path, 'rb')
                        self._xfer_name = name
                        _log().info("BLE file transfer opened: %s", name)
                    except OSError as e:
                        _log().warning("BLE file select: cannot open %s: %s", name, e)
                else:
                    _log().warning("BLE file select: index %d out of range (%d files)",
                                    index, len(entries))
                self._prepare_chunk()
                continue
            _log().warning("BLE file select: unrecognized payload (%d bytes)", len(data))

    async def run(self):
        await asyncio.gather(
            self._peripheral_task(),
            self._status_task(),
            self._control_task(),
            self._profile_task(),
            self._file_select_task(),
        )
