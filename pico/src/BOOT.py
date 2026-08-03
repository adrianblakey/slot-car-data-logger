# Copyright @ 2026, Adrian Blakey. All rights reserved
# BOOT.py — deploy-time flags and credentials.
#
# Kept on the filesystem (never frozen) so it can be edited without a
# reflash. Gitignored — never commit real credentials. Wi-Fi SSID/password
# search actually happens via conf/wifi*.json (see wifi_connection.py);
# the values here are a fallback used only if no conf/wifi*.json is found.

from micropython import const
import logging

START_WIFI: bool = True        # connect to Wi-Fi at boot
START_BLE: bool  = True        # start the BLE GATT server at boot
SSID: str = const("")          # fallback SSID (prefer conf/wifi*.json)
PWD: str  = const("")          # fallback password
OVERCLOCK = const(False)       # overclock the RP2040
LOG_LEVEL = logging.DEBUG
logging.basicConfig(level=LOG_LEVEL)
