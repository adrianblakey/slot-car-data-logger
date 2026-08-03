# Copyright @ 2026 Adrian Blakey. All rights reserved
# wifi_connection.py — Wi-Fi connect/monitor for the abbreviated UI.
#
# Adapted from the early prototype's connection.py, keeping its most useful
# trick: search /conf for every wifi*.json file (not just wifi.json), tried
# in order, so a device can carry several trackside AP credentials and use
# whichever one answers — most tracks have no Wi-Fi at all, so a driver
# provisions their own hotspot per the README, and different venues end up
# with different files. The old version was fully blocking (time.sleep()
# spin loops in connect()); this one polls asyncio.sleep_ms() so it can run
# as a normal Core 0 task alongside the buttons, BLE, and web server.

import os
import network
import time
import machine
import asyncio
import logconfig

log = None   # bound lazily so this module can be imported before configure()


def _log():
    global log
    if log is None:
        log = logconfig.get_logger("wifi")
    return log


CONF_DIR = "/conf"


def _wifi_config_files():
    """wifi.json first (if present), then any other wifi*.json, sorted."""
    try:
        all_files = sorted(f for f in os.listdir(CONF_DIR)
                            if f.startswith("wifi") and f.endswith(".json"))
    except OSError:
        return []
    if "wifi.json" in all_files:
        all_files.remove("wifi.json")
        all_files.insert(0, "wifi.json")
    return all_files


def _read_credentials(fname):
    import json
    with open(CONF_DIR + "/" + fname) as f:
        d = json.load(f)
    return d["ssid"], d["password"]


class WiFiConnection:
    def __init__(self):
        self._wlan = network.WLAN(network.STA_IF)
        self._ip = None

    def _hostname(self):
        mac = self._wlan.config('mac')
        return "slotcar-" + "".join("{:02x}".format(b) for b in mac[3:])

    async def connect(self, per_ap_timeout_s: int = 12) -> bool:
        """Try every conf/wifi*.json in turn. Returns True once connected."""
        files = _wifi_config_files()
        if not files:
            _log().info("No conf/wifi*.json files found — skipping Wi-Fi")
            return False

        self._wlan.active(True)
        self._wlan.config(pm=0xa11140)   # disable power-save (matches prototype)
        network.hostname(self._hostname())

        for fname in files:
            try:
                ssid, pwd = _read_credentials(fname)
            except Exception as e:
                _log().warning("Bad wifi config %s: %s", fname, e)
                continue

            _log().info("Connecting to %s (from %s)...", ssid, fname)
            self._wlan.connect(ssid, pwd)
            deadline = time.ticks_add(time.ticks_ms(), per_ap_timeout_s * 1000)
            while (self._wlan.status() != network.STAT_GOT_IP
                    and time.ticks_diff(deadline, time.ticks_ms()) > 0):
                await asyncio.sleep_ms(250)

            if self._wlan.status() == network.STAT_GOT_IP:
                self._ip = self._wlan.ifconfig()[0]
                _log().info("Wi-Fi connected: %s as %s", ssid, self._ip)
                return True
            _log().info("Failed to connect to %s, trying next", ssid)

        self._wlan.active(False)
        return False

    def ip(self):
        if self._ip is None and self._wlan.status() == network.STAT_GOT_IP:
            self._ip = self._wlan.ifconfig()[0]
        return self._ip

    def connected(self) -> bool:
        return self._wlan.isconnected()

    async def monitor(self, interval_s: int = 10) -> None:
        """Log link drops; does not attempt to reconnect (matches the
        reference's Wi-Fi task scope — reconnect logic is future work)."""
        while True:
            await asyncio.sleep(interval_s)
            if not self.connected():
                _log().warning("Wi-Fi link dropped")
                self._ip = None
