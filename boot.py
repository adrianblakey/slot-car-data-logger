# Copyright @ 20023, Adrian Blakey. All rights reserved

import network
import os
import time
import socket
from machine import Pin
import errno

from config import SSID, PASSWORD, MODES
import logging

log = logging.getLogger("boot")


class Connection():
    
    def __init__(self, ssid: str, password: str, retries: int = 20, debug: bool = True):
        self._ssid = ssid
        self._password = password
        self._retries = retries
        self._debug = debug
        
        
    def connect(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.config(pm = 0xa11140)  # Disable power-save
        wlan.connect(self._ssid, self._password)
        if self._debug:
            log.debug('Connecting to ' + self._ssid)
        
        while self._retries > 0 and wlan.status() != network.STAT_GOT_IP:
            self._retries -= 1
            time.sleep(1)    
        
        if wlan.status() != network.STAT_GOT_IP:
            if self._debug:
                log.debug('Connection failed. Check ssid and password')
            raise RuntimeError('WLAN connection failed')
        else:
            if self._debug:
                log.debug('Connected. IP Address = ' + wlan.ifconfig()[0])


    def test(self):
        log.debug("Test connection")
        try:
            addr = socket.getaddrinfo('www.google.com', 443)[0][-1]
            log.debug("Ping addr OK" + str(addr))
        except OSError as err:
            log.debug("No network connection " + str(err.errno))
            if err.errno == errno.ENXIO: #  no network available
                log.debug("No network connection")
                
Pin("LED",Pin.OUT,value=1)
print('MODES', MODES)
if 'web' in MODES:
    if log.getEffectiveLevel() == logging.DEBUG:
        log.debug("Connecting to wifi")
    conn = Connection(SSID, PASSWORD)
    conn.connect()
    conn.test()
