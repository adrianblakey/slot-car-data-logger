# Copyright @ 2023, Adrian Blakey. All rights reserved
# Connect to WiFi
import network
import os
import time
import socket
from machine import Pin
import errno
from led import Led, red_led, yellow_led
from config import Config

the_config: Config = Config()

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
        self._password = password
        wlan = network.WLAN(network.STA_IF)
        if wlan.status() == network.STAT_GOT_IP:
            self._connected = True
            self._ip = wlan.ifconfig()[0]
            log.debug('Already connected. IP Address: %s', self._ip)
            return self._ip
        wlan.active(True)
        wlan.config(pm = 0xa11140)  # Disable power-save
        mac = wlan.config('mac')
        #host = 'slot-car-logger-' + ''.join('{:02x}'.format(b) for b in mac[3:])
        host = 'slot-car-logger-' + the_config.my_id()[0:8]
        network.hostname(host)
        log.debug('Connecting to %s current status: %s hostname %s', self._ssid, str(wlan.status()), host)
        red_led.off()
        yellow_led.on()
        wlan.connect(self._ssid, self._password)
        i: int = self._retries
        while i > 0 and wlan.status() != network.STAT_GOT_IP:
            self._state(wlan)
            red_led.toggle()
            yellow_led.toggle()
            i -= 1
            time.sleep(1)
        if wlan.status() != network.STAT_GOT_IP:
            log.info('Connection failed. Check ssid and password')
            self._connected = False
            self._ip = None
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
    
    def test(self) -> None:
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

    def set_ids(self, ssid: str, pwd: str) -> None:
        self._ssid = ssid
        self._pwd = pwd
     
    def get_connection(self) -> None:
        log.debug('Get connection')
        ssid, pwd = the_config.read_conn()
        while True:
            if ssid == None and pwd == None:
                break
            self.set_ids(ssid, pwd)
            log.debug("Attempting to connect to wifi with %s %s", ssid, pwd)
            self.connect(ssid, pwd)
            if self.connected():
                log.debug('Connected %s %s', ssid, pwd)
                break
            else:
                log.debug('No connection')
            ssid, pwd = the_config.read_conn()
        
if __name__ == "__main__":
    try:
        the_connection
        log.debug('Existing connection %s', the_connection)
    except NameError:
        log.info('the_connection not yet defined')
        the_connection = Connection()
    if the_connection.connected():
        pass
    else:
        the_connection.get_connection()
    the_connection.test()