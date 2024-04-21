# Copyright @ 20023, Adrian Blakey. All rights reserved
# Runs everytime - so config Wifi, mount sd

import os
from machine import Pin, SPI
from config import Config
import logging
import time
import ntptime
from connection import Connection
from sdcard import SDCard

log = logging.getLogger("boot")
log.info('Starting boot')

the_config = Config()
the_connection = Connection()
the_connection.get_connection()

if the_connection.connected():
    log.debug("Local time before synchronization：%s" %str(time.localtime()))
    ntptime.settime()
    log.debug("Local time after synchronization：%s" %str(time.localtime()))
else:
    log.debug('Not connected')

try:
    spi, sck, mosi, miso, cs, baudrate = the_config.get_sdcard()
    log.debug('spi %s, sck %s, mosi %s, miso %s, cs %s, baudrate %s', spi, sck, mosi, miso, cs, baudrate)
    sd  = SDCard(spi, sck, mosi) #, miso) # =cs, baudrate=baudrate)
    log.debug('Attempting to mount sd card ...')
    sd.mount()
    log.debug('sd state %s', sd.state())
except AttributeError as ex:
    log.info('No sd card %s', ex)
    
Pin("LED", Pin.OUT).on()


