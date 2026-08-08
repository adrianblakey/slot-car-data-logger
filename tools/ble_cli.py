#!/usr/bin/env python3
# Copyright @ 2026 Adrian Blakey. All rights reserved
# tools/ble_cli.py — command-line client for every BLE function the Pico W
# exposes (pico/src/ble_server.py): status, capture/erase/Wi-Fi/lane/race
# control, profile read/write, and the Files service (list + download
# session data / syslog files) — a BLE-only equivalent of the web UI, for
# when there's no Wi-Fi to reach that with.
#
# UUIDs/command bytes/wire protocol below are copied from ble_server.py, not
# imported from it — this runs on a host, that runs on the device under
# MicroPython. Keep the two in sync by hand; see README's "BLE control
# characteristic" and "BLE file transfer" for the protocol this implements.
#
# Usage:
#   pip install bleak
#   python3 tools/ble_cli.py scan
#   python3 tools/ble_cli.py status
#   python3 tools/ble_cli.py start / stop / mark / erase
#   python3 tools/ble_cli.py wifi-start / wifi-stop
#   python3 tools/ble_cli.py lane-rotate / lane-set 5 / race-toggle
#   python3 tools/ble_cli.py profile
#   python3 tools/ble_cli.py profile --set track=Daytona --set lane=3
#   python3 tools/ble_cli.py list-files
#   python3 tools/ble_cli.py download session_20260101_120000.bin
#
# All commands except scan take --address to connect directly (skips
# scanning — faster once you know the device's address) and --timeout for
# the scan itself.

import argparse
import asyncio
import json
import struct
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("This tool needs bleak: pip install bleak", file=sys.stderr)
    sys.exit(1)

DEVICE_NAME_PREFIX = "SCLogger-"

# Device Information service (standard).
FW_REV_UUID  = "00002a26-0000-1000-8000-00805f9b34fb"
MFG_UUID     = "00002a29-0000-1000-8000-00805f9b34fb"
SER_UUID     = "00002a25-0000-1000-8000-00805f9b34fb"
SW_REV_UUID  = "00002a28-0000-1000-8000-00805f9b34fb"

# Logger service (custom).
STATUS_UUID  = "b1190efb-176f-4b32-a715-89b3425a4076"
CONTROL_UUID = "b1190efc-176f-4b32-a715-89b3425a4076"
PROFILE_UUID = "b1190efd-176f-4b32-a715-89b3425a4076"

# Files service (custom).
FILE_SELECT_UUID = "b1190f02-176f-4b32-a715-89b3425a4076"
FILE_CHUNK_UUID  = "b1190f03-176f-4b32-a715-89b3425a4076"

STATUS_FMT = "<BBHB"   # recording, flash_free_pct, record_count, wifi_up

CMD_STOP, CMD_START, CMD_MARK, CMD_ERASE = 0, 1, 2, 3
CMD_WIFI_START, CMD_WIFI_STOP = 4, 5
CMD_LANE_ROTATE, CMD_LANE_SET, CMD_RACE_TOGGLE = 6, 7, 8

CTRL_NEXT = b"\x00"
CTRL_LIST = b"\x01"
CTRL_SELECT = 0x02

# Minimum delay between writing "advance" and reading the next chunk.
# Confirmed on hardware (see README's "found and fixed on hardware" #15):
# reading back-to-back with no delay intermittently produces a torn read —
# not a dropped chunk, but content from a different point in the file
# spliced into the middle of another chunk. ~150ms confirmed clean.
CHUNK_PACING_S = 0.15

PROFILE_FIELDS = ("track", "race", "lane", "controller", "car")


def decode_status(raw: bytes) -> dict:
    recording, flash_pct, record_count, wifi_up = struct.unpack(STATUS_FMT, bytes(raw))
    return {
        "recording": bool(recording),
        "flash_free_pct": flash_pct,
        "record_count": record_count,
        "wifi_up": bool(wifi_up),
    }


async def find_device(name_filter: str, timeout: float):
    print("Scanning for {}* ({}s)...".format(DEVICE_NAME_PREFIX, timeout), file=sys.stderr)
    devices = await BleakScanner.discover(timeout=timeout)
    matches = [d for d in devices if d.name and d.name.startswith(name_filter)]
    if not matches:
        print("No device found matching '{}*'".format(name_filter), file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print("Multiple devices found, using the first:", file=sys.stderr)
        for d in matches:
            print("  {} ({})".format(d.name, d.address), file=sys.stderr)
    return matches[0]


async def connect(args) -> BleakClient:
    """Returns an unconnected BleakClient — callers use it as an `async
    with` context manager, which connects on __aenter__. Connecting here
    too would double-connect (BleakError: Client is already connected)."""
    address = args.address
    if address is None:
        dev = await find_device(DEVICE_NAME_PREFIX, args.timeout)
        address = dev.address
        print("Connecting to {} ({})...".format(dev.name, address), file=sys.stderr)
    return BleakClient(address)


async def write_control(client: BleakClient, cmd: int, payload: bytes = b"") -> None:
    await client.write_gatt_char(CONTROL_UUID, bytes([cmd]) + payload, response=True)


async def read_status(client: BleakClient) -> dict:
    return decode_status(await client.read_gatt_char(STATUS_UUID))


async def read_profile(client: BleakClient) -> dict:
    raw = await client.read_gatt_char(PROFILE_UUID)
    return json.loads(raw.decode())


async def pull_chunks(client: BleakClient) -> bytes:
    """Read FILE_CHUNK, write CTRL_NEXT, repeat until a chunk comes back
    empty — whatever was most recently selected on FILE_SELECT (a real
    file, or the file listing itself). See CHUNK_PACING_S."""
    data = bytearray()
    while True:
        chunk = await client.read_gatt_char(FILE_CHUNK_UUID)
        if not chunk:
            break
        data += chunk
        await client.write_gatt_char(FILE_SELECT_UUID, CTRL_NEXT, response=True)
        await asyncio.sleep(CHUNK_PACING_S)
    return bytes(data)


async def fetch_file_list(client: BleakClient) -> list:
    await client.write_gatt_char(FILE_SELECT_UUID, CTRL_LIST, response=True)
    await asyncio.sleep(CHUNK_PACING_S)
    raw = await pull_chunks(client)
    return json.loads(raw.decode()) if raw else []


async def download_by_index(client: BleakClient, index: int) -> bytes:
    payload = bytes([CTRL_SELECT, index & 0xFF, (index >> 8) & 0xFF])
    await client.write_gatt_char(FILE_SELECT_UUID, payload, response=True)
    await asyncio.sleep(CHUNK_PACING_S)
    return await pull_chunks(client)


# ── subcommands ──────────────────────────────────────────────────────────

async def cmd_scan(args) -> None:
    devices = await BleakScanner.discover(timeout=args.timeout)
    matches = [d for d in devices if d.name and d.name.startswith(DEVICE_NAME_PREFIX)]
    if not matches:
        print("No SCLogger device found")
        return
    for d in matches:
        print("{}  {}".format(d.address, d.name))


async def cmd_info(args) -> None:
    async with await connect(args) as client:
        mfg = (await client.read_gatt_char(MFG_UUID)).decode()
        ser = (await client.read_gatt_char(SER_UUID)).decode()
        fw = (await client.read_gatt_char(FW_REV_UUID)).decode()
        sw = (await client.read_gatt_char(SW_REV_UUID)).decode()
        print("Manufacturer:     ", mfg)
        print("Serial (device id):", ser)
        print("Firmware rev:     ", fw, "  (format: <ip or -> <MicroPython version>)")
        print("Software rev:     ", sw)


async def cmd_status(args) -> None:
    async with await connect(args) as client:
        if not args.watch:
            print(json.dumps(await read_status(client), indent=2))
            return

        print("Watching status (Ctrl-C to stop)...", file=sys.stderr)
        seen = asyncio.Event()
        latest = {}

        def on_notify(_handle, data):
            latest.clear()
            latest.update(decode_status(data))
            seen.set()

        await client.start_notify(STATUS_UUID, on_notify)
        try:
            while True:
                await seen.wait()
                seen.clear()
                print(json.dumps(latest))
        except KeyboardInterrupt:
            pass
        finally:
            await client.stop_notify(STATUS_UUID)


async def cmd_profile(args) -> None:
    async with await connect(args) as client:
        if args.set:
            updates = {}
            for item in args.set:
                if "=" not in item:
                    print("--set expects key=value, got: {!r}".format(item), file=sys.stderr)
                    sys.exit(1)
                key, value = item.split("=", 1)
                if key not in PROFILE_FIELDS:
                    print("Unknown profile field {!r} (valid: {})".format(
                        key, ", ".join(PROFILE_FIELDS)), file=sys.stderr)
                    sys.exit(1)
                updates[key] = int(value) if key == "lane" else value
            await client.write_gatt_char(PROFILE_UUID, json.dumps(updates).encode(), response=True)
            await asyncio.sleep(0.3)
        print(json.dumps(await read_profile(client), indent=2))


async def cmd_simple_control(args) -> None:
    """start/stop/mark/erase/wifi-stop — write the command, then print
    status so you can see the effect."""
    async with await connect(args) as client:
        await write_control(client, args._cmd)
        await asyncio.sleep(2.5)   # main.py's status characteristic refreshes every 2s
        print(json.dumps(await read_status(client), indent=2))


async def cmd_wifi_start(args) -> None:
    """Real Wi-Fi connection takes several seconds (confirmed ~6-8s in
    testing), not the ~2.5s a plain status check waits — poll instead of
    a single check, so a slow-but-successful connect doesn't look like a
    silent failure. wifi_up staying False the whole window means either
    the free-heap check refused (see CONFIG.WIFI_MIN_FREE_BYTES) or no
    known conf/wifi*.json network was in range — check the device's own
    log for which."""
    async with await connect(args) as client:
        await write_control(client, CMD_WIFI_START)
        st = None
        for _ in range(15):
            await asyncio.sleep(1.0)
            st = await read_status(client)
            if st["wifi_up"]:
                break
        print(json.dumps(st, indent=2))
        if not st["wifi_up"]:
            print("Wi-Fi did not come up within 15s — refused (free-heap check) "
                  "or no known network in range", file=sys.stderr)


async def cmd_profile_control(args) -> None:
    """lane-rotate/race-toggle — write the command, then print PROFILE
    (not status: lane/race live there, not in the status characteristic,
    and main.py's refresh_profile() pushes the new value immediately, no
    2s status-refresh wait needed)."""
    async with await connect(args) as client:
        await write_control(client, args._cmd)
        await asyncio.sleep(0.3)
        print(json.dumps(await read_profile(client), indent=2))


async def cmd_lane_set(args) -> None:
    if not (1 <= args.lane <= 8):
        print("Lane must be 1-8", file=sys.stderr)
        sys.exit(1)
    async with await connect(args) as client:
        await write_control(client, CMD_LANE_SET, bytes([args.lane]))
        await asyncio.sleep(0.3)
        print(json.dumps(await read_profile(client), indent=2))


async def cmd_list_files(args) -> None:
    async with await connect(args) as client:
        files = await fetch_file_list(client)
        if args.json:
            print(json.dumps(files, indent=2))
            return
        if not files:
            print("No files on device")
            return
        for i, f in enumerate(files):
            print("[{:3d}] {:>4}  {:>8} bytes  {}".format(i, f["kind"], f["size"], f["name"]))


async def cmd_download(args) -> None:
    async with await connect(args) as client:
        files = await fetch_file_list(client)
        index = next((i for i, f in enumerate(files) if f["name"] == args.name), None)
        if index is None:
            print("'{}' not found on device. Run list-files to see what's there.".format(
                args.name), file=sys.stderr)
            sys.exit(1)
        size = files[index]["size"]
        out_path = args.output or args.name
        print("Downloading {} ({} bytes) -> {}".format(args.name, size, out_path), file=sys.stderr)
        data = await download_by_index(client, index)
        if len(data) != size:
            print("WARNING: downloaded {} bytes, device listed {} bytes".format(
                len(data), size), file=sys.stderr)
        with open(out_path, "wb") as f:
            f.write(data)
        print("Wrote {} bytes to {}".format(len(data), out_path), file=sys.stderr)


# ── argument parsing ─────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--address", help="connect directly by BLE address, skip scanning")
        sp.add_argument("--timeout", type=float, default=6.0, help="scan timeout in seconds (default 6)")

    sp = sub.add_parser("scan", help="list nearby SCLogger devices")
    sp.add_argument("--timeout", type=float, default=6.0)
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("info", help="Device Information characteristics")
    add_common(sp)
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("status", help="read (or --watch) the status characteristic")
    add_common(sp)
    sp.add_argument("--watch", action="store_true", help="stream live status updates until Ctrl-C")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("profile", help="read, or --set, the race session profile")
    add_common(sp)
    sp.add_argument("--set", action="append", metavar="KEY=VALUE",
                     help="set a profile field (track/race/lane/controller/car); repeatable")
    sp.set_defaults(func=cmd_profile)

    simple = (
        ("start", CMD_START, "start capture (new session file)"),
        ("stop", CMD_STOP, "stop capture"),
        ("mark", CMD_MARK, "lap marker (only while capturing)"),
        ("erase", CMD_ERASE, "erase all session data and old log files (refused while capturing)"),
        ("wifi-stop", CMD_WIFI_STOP, "stop Wi-Fi, back to BLE-only"),
    )
    for name, cmd, help_text in simple:
        sp = sub.add_parser(name, help=help_text)
        add_common(sp)
        sp.set_defaults(func=cmd_simple_control, _cmd=cmd)

    sp = sub.add_parser("wifi-start", help="start Wi-Fi over BLE (gated by a free-heap check); polls up to 15s")
    add_common(sp)
    sp.set_defaults(func=cmd_wifi_start)

    profile_ctrl = (
        ("lane-rotate", CMD_LANE_ROTATE, "advance to the next lane colour"),
        ("race-toggle", CMD_RACE_TOGGLE, "flip practice <-> race"),
    )
    for name, cmd, help_text in profile_ctrl:
        sp = sub.add_parser(name, help=help_text)
        add_common(sp)
        sp.set_defaults(func=cmd_profile_control, _cmd=cmd)

    sp = sub.add_parser("lane-set", help="set lane to a specific number (1-8)")
    add_common(sp)
    sp.add_argument("lane", type=int)
    sp.set_defaults(func=cmd_lane_set)

    sp = sub.add_parser("list-files", help="list session data (.bin) and log (.log) files")
    add_common(sp)
    sp.add_argument("--json", action="store_true", help="raw JSON instead of a table")
    sp.set_defaults(func=cmd_list_files)

    sp = sub.add_parser("download", help="download a file by its exact name (see list-files)")
    add_common(sp)
    sp.add_argument("name")
    sp.add_argument("-o", "--output", help="output path (default: same name, current directory)")
    sp.set_defaults(func=cmd_download)

    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        asyncio.run(args.func(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
