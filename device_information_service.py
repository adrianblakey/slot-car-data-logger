# Copyright @ 20023, Adrian Blakey. All rights reserved
# BT device information service
# TODO - not used - better way to refactor main

from bluetooth import UUID
from aioble import Service, Characteristic
import logging
log = logging.getLogger("device_information_service")
global the_device_information_service
global name_char
global serial_char
global firmware_char
global software_char

try:
    the_device_information_service = Service(UUID(0x180A))
    name_char = Characteristic(the_device_information_service, UUID(0x2A29), read=True)
    serial_char = Characteristic(the_device_information_service, UUID(0x2A25), read=True)
    firmware_char = Characteristic(the_device_information_service, UUID(0x2A26), read=True)
    software_char = Characteristic(the_device_information_service, UUID(0x2A28), read=True)
except NameError:
    log.info('the_device_information_service not yet defined')
  

log.debug('Device information service %s', the_device_information_service)


