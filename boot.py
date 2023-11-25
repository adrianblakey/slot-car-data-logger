# Copyright @ 20023, Adrian Blakey. All rights reserved
# Runs everytime - so config Wifi, mount sd?

import os
from machine import Pin, SPI
from config import Config
import logging
from connection import Connection
from sdcard import SDCard

log = logging.getLogger("boot")
log.info('Starting boot')

the_config = Config()
the_connection = Connection()

ssid, pwd = the_config.read_conn()
while True:
    if ssid == None and pwd == None:
        break
    if the_connection.connect(ssid, pwd) != '':
        break
    ssid, pwd = the_config.read_conn()

if not the_connection.connected():
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



