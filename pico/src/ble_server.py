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
import struct
import asyncio
import aioble
import bluetooth
import machine

from session_profile import PROFILE
import logconfig

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

_ADV_APPEARANCE_LOGGER = 128   # org.bluetooth.characteristic.gap.appearance "Generic Computer"

# Control command bytes written by a central.
CMD_STOP  = 0
CMD_START = 1
CMD_MARK  = 2

_STATUS_FMT = '<BBH'   # recording(0/1), flash_free_pct(0-100), record_count(u16, wraps)


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

        aioble.register_services(self._device_svc, self._logger_svc)

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
            async with await aioble.advertise(
                _ADV_INTERVAL_MS,
                name="SCLogger-" + self._device_id[0:6],
                services=[_DEVICE_SVC_UUID, _LOGGER_SVC_UUID],
                appearance=_ADV_APPEARANCE_LOGGER,
            ) as connection:
                _log().info("BLE connection from %s", connection.device)
                self._connection = connection
                self._refresh_fw_rev()
                if self._on_connect is not None:
                    try:
                        self._on_connect()
                    except Exception:
                        pass
                while connection.is_connected():
                    await asyncio.sleep_ms(2000)
                self._connection = None

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
                        st.get('record_count', 0) & 0xFFFF)
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
                    self._control_fn(cmd)
                except Exception as e:
                    _log().warning("BLE control handler failed: %s", e)

    # ── profile read/write ──────────────────────────────────────────────────

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

    async def run(self):
        await asyncio.gather(
            self._peripheral_task(),
            self._status_task(),
            self._control_task(),
            self._profile_task(),
        )
