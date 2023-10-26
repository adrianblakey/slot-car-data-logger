import sys

sys.path.append("")
from micropython import const

import aioble
import bluetooth

import random
import struct

import uasyncio as asyncio
from microdot_asyncio import Microdot, Response, send_file
import microdot_utemplate
from microdot_asyncio_websocket import with_websocket
import microdot_websocket
from device import Device, the_device
import time
import logging
import config
from config import MODES

from button import Button
from led import Led, yellow_led, red_led
from logging_state import Logging_State
from log_file import Log_File

log = logging.getLogger("main")
if 'web' in MODES:
    from webserver import server
    
    
logging_state = Logging_State()  # logging state obj - intially off    
yellow_button = Button(22, False, logging_state.callback)

yellow_led = Led(18)
red_led = Led(17)

_LOGGER_UUID = bluetooth.UUID('B1190EF7-176F-4B32-A715-89B3425A4076') # Custom service vendor-specific UUID
_LOGGER_PROFILE_SEND_UUID = bluetooth.UUID('B1190EF8-176F-4B32-A715-89B3425A4076')  # Transmit data
_LOGGER_PROFILE_RECV_UUID = bluetooth.UUID('B1190EF9-176F-4B32-A715-89B3425A4076')  # Receive data
_ADV_APPEARANCE_LOGGER = const(768)

_ADV_INTERVAL_MS = 250_000

# Register GATT server.
logger_service = aioble.Service(_LOGGER_UUID)
profile_send_characteristic = aioble.Characteristic(logger_service, _LOGGER_PROFILE_SEND_UUID, read=True, notify=True)
profile_recv_characteristic = aioble.Characteristic(logger_service, _LOGGER_PROFILE_RECV_UUID, write=True, read=True, notify=True, capture=True, indicate=True)
aioble.register_services(logger_service)


# Serially wait for connections. Don't advertise while a central is
# connected.
async def peripheral_task():
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="slot-car-logger",
            services=[_LOGGER_UUID],
            appearance=_ADV_APPEARANCE_LOGGER,
            manufacturer=(0xabcd, b"1234"),
        ) as connection:
            if log.getEffectiveLevel() == logging.DEBUG:
                log.debug("Connection from %s", connection.device)
            while connection.is_connected() == True:
                await asyncio.sleep_ms(1000)


# Helper to encode the profile (sint16, profile index number).
def _encode_profile(profile):
    return struct.pack("<h", int(profile))


# Periodically poll the bt profile config
async def profile_task():
    while True:
        profile_send_characteristic.write(_encode_profile(config.PROFILE))
        await asyncio.sleep_ms(5000)


async def receive_task():
    while True:
        connection, data = await profile_recv_characteristic.written()
        new_profile = int.from_bytes(data, 'little')
        # unp = struct.unpack("<h", data)
        if log.getEffectiveLevel() == logging.DEBUG:
            log.debug("Received connection from %s", connection.device)
            log.debug("Received data %s", str(new_profile))
        profile_recv_characteristic.write(_encode_profile(config.PROFILE))
        profile_recv_characteristic.notify(connection)
        await asyncio.sleep(1)


def set_global_exception():
    def handle_exception(loop, context):
        import sys
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
    

# Data collection start/stop - check every 200mSecs
async def yellow_button_task():
    while True:
        yellow_button.update()
        await asyncio.sleep_ms(200)
        
  
# Read the device, log to disk 
async def log_data_task():
    while True:
        if logging_state.on():
            logging_state.get_file().log(the_device.read_all())
        await asyncio.sleep_ms(100)    
            
             
async def main():
    set_global_exception()  # Debug aid
    tasks = list()
    if 'web' in MODES:
        tasks.append(asyncio.create_task(server.start_server(host='0.0.0.0', port=80, debug=True, ssl=None)))
    tasks.append(asyncio.create_task(peripheral_task()))
    tasks.append(asyncio.create_task(profile_task()))
    tasks.append(asyncio.create_task(receive_task()))
    tasks.append(asyncio.create_task(yellow_button_task()))
    tasks.append(asyncio.create_task(log_data_task()))
    res = await asyncio.gather(*tasks)

    
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
