# Copyright @ 2023, Adrian Blakey. All rights reserved
# Connect to WiFi
import network
import os
import time
import socket
from machine import Pin
import errno
from led import Led, red_led, yellow_led

import logging

log = logging.getLogger("connection")

class Connection():
    
    def __init__(self, retries: int = 5, debug: bool = True):
        self._ssid = None
        self._retries = retries
        self._connected = None
        self._ip = None

    def _state(self, wlan):
        if wlan.status() == network.STAT_IDLE:
            log.debug('stat idle')
        elif network.STAT_CONNECTING:
            log.debug('stat connecting')
        elif network.STAT_WRONG_PASSWORD:
            log.debug('stat wrong pwd')
        elif network.STAT_NO_AP_FOUND:
            log.debug('stat no ap found')
        elif network.STAT_CONNECT_FAIL:
            log_debug('state connect fail')
        elif network.STAT_GOT_IP:
            log_debug('state git ip')
        else:
            log_debug('no known state')
        
    def connect(self, ssid: str, password: str) -> str:
        self._ssid = ssid
        wlan = network.WLAN(network.STA_IF)
        if wlan.status() == network.STAT_GOT_IP:
            self._connected = True
            self._ip = wlan.ifconfig()[0]
            log.debug('Already connected. IP Address: %s', self._ip)
            return self._ip
        wlan.active(True)
        wlan.config(pm = 0xa11140)  # Disable power-save
        mac = wlan.config('mac')
        host = 'slot-car-logger-' + ''.join('{:02x}'.format(b) for b in mac[3:])
        network.hostname(host)
        log.debug('Connecting to %s current status: %s hostname %s', self._ssid, str(wlan.status()), host)
        red_led.off()
        yellow_led.on()
        wlan.connect(self._ssid, password)
        i: int = self._retries
        while i > 0 and wlan.status() != network.STAT_GOT_IP:
            red_led.toggle()
            yellow_led.toggle()
            i -= 1
            time.sleep(1)
        if wlan.status() != network.STAT_GOT_IP:
            log.info('Connection failed. Check ssid and password')
            self._connected = False
            wlan.active(False)
        else:
            self._connected = True
            self._ip = wlan.ifconfig()[0]
            log.debug('Wifi connected as {}/{}, net={}, gw={}, dns={}'.format(host, *wlan.ifconfig()))
        red_led.off()
        yellow_led.off()
        return self._ip

    def ip(self) -> str:
        if self._ip == None:
            wlan = network.WLAN(network.STA_IF)
            if wlan.status() == network.STAT_GOT_IP:
                self._ip = network.WLAN(network.STA_IF).ifconfig()[0]
        return self._ip
    
    def connected(self) -> bool:
        if self._connected == None:
            self.test()
        return self._connected
    
    def test(self):
        log.debug("Test connection")
        try:
            addr = socket.getaddrinfo('www.google.com', 443)[0][-1]
            self._connected = True
            log.debug("Ping addr OK" + str(addr))
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




