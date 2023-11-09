# Copyright @ 20023, Adrian Blakey. All rights reserved
# Runs everytime - so config Wifi, mount sd?

import os
from machine import Pin
from config import Config
import logging
from connection import Connection

log = logging.getLogger("boot")
log.info('Starting boot')

the_config = Config()
the_connection = Connection()

ssid, pwd = the_config.read_conn()
while True:
    if ssid == None and pwd == None:
        break
    the_connection.set_ids(ssid, pwd)
    the_connection.connect()
    ssid, pwd = the_config.read_conn()
    
if the_connection.connected():
    pass
else:
    log.debug('Not connected')

try:
    log.debug('Attempting to mount sd card ...')
    os.mount(machine.SDCard(), "/sd")
except AttributeError as ex:
    log.info('No sd card %s', ex)
    
Pin("LED", Pin.OUT).on()

