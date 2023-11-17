# Copyright @ 2023, Adrian Blakey. All rights reserved
# Connect to WiFi
import network
import os
import time
import socket
from machine import Pin
import errno

import logging

log = logging.getLogger("connection")


class Connection():
    
    def __init__(self, retries: int = 20, debug: bool = True):
        self._ssid = None
        self._password = None
        self._retries = retries
        self._connected = None
        
        
    def set_ids(self, ssid: str, password: str):
        self._ssid = ssid
        self._password = password
        
        
    def connect(self):
        wlan = network.WLAN(network.STA_IF)
        if wlan.status() == network.STAT_GOT_IP:
            self._connected = True
            log.debug('Already connected. IP Address: %s', wlan.ifconfig()[0])
            return
        wlan.active(True)
        wlan.config(pm = 0xa11140)  # Disable power-save
        log.debug('Connecting to ' + self._ssid)
        wlan.connect(self._ssid, self._password)
        while self._retries > 0 and wlan.status() != network.STAT_GOT_IP:
            self._retries -= 1
            time.sleep(1)    
        if wlan.status() != network.STAT_GOT_IP:
            log.info('Connection failed. Check ssid and password')
            self._connected = False
        else:
            self._connected = True
            log.info('Connected. IP Address: %s', wlan.ifconfig()[0])

    def ip(self) -> str:
        return network.WLAN(network.STA_IF).ifconfig()[0]
    
    def connected(self):
        if self._connected == None:
            self.test()
        return self._connected
    
    def test(self):
        log.debug("Test connection")
        try:
            addr = socket.getaddrinfo('www.google.com', 443)[0][-1]
            self._connected = True
            log.info("Ping addr OK" + str(addr))
        except OSError as err:
            self._connected = False
            log.debug("No network connection " + str(err.errno))
            if err.errno == errno.ENXIO: #  no network available
                log.info("No network connection")


if __name__ == "__main__":
    Pin("LED", Pin.OUT,value=1)

    try:
        the_connection
    except NameError:
        log.info('the_connection not yet defined')
        the_connection = Connection()
        log.debug("Attempting to connect to wifi")
        the_connection.connect()
        if the_connection.connected():
            the_connection.test()




