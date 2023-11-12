# Copyright @ 2023, Adrian Blakey. All rights reserved
# Runs the app
import sys

sys.path.append("")

from micropython import const
from machine import Pin
import aioble
import bluetooth

import random
import struct

import uasyncio as asyncio
from microdot_asyncio import Microdot, Response, send_file
import microdot_utemplate
from microdot_asyncio_websocket import with_websocket
import microdot_websocket

import time
import logging
from buzzer import Buzzer, the_buzzer

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("main")
log.info('Starting main')

from context import Context, the_context
from config import Config


the_config = Config()
the_config.read_profiles()
log.info('The config object %s', the_config)

the_context.put('config', the_config)

from connection import Connection
from device import Device, the_device
from button import Button
from led import Led, yellow_led, red_led
from logging_state import Logging_State
from log_file import Log_File 

yellow_logging_state = Logging_State(the_config)  # logging state obj - intially off    
yellow_button = Button(22, False, yellow_logging_state.yellow_callback)
black_logging_state = Logging_State(the_config)  # logging state obj - intially off
black_button = Button(16, False, black_logging_state.black_callback)

the_connection = Connection()
if the_connection.connected():
    log.debug('Import a webserver')
    from webserver import server, the_foo
    the_foo.set_state(black_logging_state)
else:
    log.debug('No network - no webserver')

_LOGGER_UUID = bluetooth.UUID('B1190EF7-176F-4B32-A715-89B3425A4076') # Custom service vendor-specific UUID
_LOGGER_PROFILE_SEND_UUID = bluetooth.UUID('B1190EF8-176F-4B32-A715-89B3425A4076')  # Transmit data
_LOGGER_PROFILE_RECV_UUID = bluetooth.UUID('B1190EF9-176F-4B32-A715-89B3425A4076')  # Receive data

# Device service uuids
_DEVICE_UUID = bluetooth.UUID(0x180A)
_DEVICE_MFG_NAME_STR = bluetooth.UUID(0x2A29)
_DEVICE_SER_NUM_STR = bluetooth.UUID(0x2A25)
_DEVICE_FW_REV_STR = bluetooth.UUID(0x2A26)
_DEVICE_SW_REV_STR = bluetooth.UUID(0x2A28)

_ADV_APPEARANCE_LOGGER = const(128) # generic computer org.bluetooth.characteristic.gap.appearance.xml 

_ADV_INTERVAL_MS = 250_000

# Register GATT server.
logger_service = aioble.Service(_LOGGER_UUID)
device_information_service = aioble.Service(_DEVICE_UUID)

profile_send_characteristic = aioble.Characteristic(logger_service, _LOGGER_PROFILE_SEND_UUID, read=True, notify=True)
profile_recv_characteristic = aioble.Characteristic(logger_service, _LOGGER_PROFILE_RECV_UUID, write=True, read=True, notify=True, capture=True, indicate=True)

# Device characteristics
device_send_mfg = aioble.Characteristic(device_information_service, _DEVICE_MFG_NAME_STR, read=True)
device_send_ser = aioble.Characteristic(device_information_service, _DEVICE_SER_NUM_STR, read=True)
device_send_fw = aioble.Characteristic(device_information_service, _DEVICE_FW_REV_STR, read=True)
device_send_sw = aioble.Characteristic(device_information_service, _DEVICE_SW_REV_STR, read=True)

aioble.register_services(logger_service, device_information_service)


# Serially wait for connections. Don't advertise while a central is
# connected.
async def peripheral_task():
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="Slot Car Logger " + the_config.my_id()[0:8], 
            services=[_LOGGER_UUID, _DEVICE_UUID],
            appearance=_ADV_APPEARANCE_LOGGER
        ) as connection:
            log.debug("Connection from %s", connection.device)
            while connection.is_connected() == True:
                await asyncio.sleep_ms(1000)


# Helper to encode the profile id (sint16, profile index number).
def _encode_profile(id: int):
    return struct.pack("<h", int(id))


async def send_my_device_task():
    # Send my bt device characteristic
    log.debug("Send device on bt")
    while True:
        device_send_mfg.write(struct.pack("<42s", "Adrian's And Richard's Technologies (AART)"))
        device_send_ser.write(struct.pack("<30s", the_config.my_id()))
        device_send_fw.write(struct.pack("<40s", sys.version))
        device_send_sw.write(struct.pack("<30s", 'Slot Car Logger; V1.0alpha'))
        await asyncio.sleep_ms(20000)


# Periodically poll the bt profile config and send it
async def profile_task():
    while True:
        profile_send_characteristic.write(_encode_profile(the_config.get_profile().id()))
        await asyncio.sleep_ms(5000)


async def receive_task():
    while True:
        connection, data = await profile_recv_characteristic.written()
        profile_id = int.from_bytes(data, 'little')
        #unp = struct.unpack("<h", data)
        log.debug("Received connection from %s", connection.device)
        log.debug("Received data %s", str(profile_id))
        id = the_config.get_profile().id()
        try:
            the_config.use_id(profile_id)
            id = profile_id
        except ValueError as ex:
            log.debug('Not a profile id %s', ex)
        profile_recv_characteristic.write(_encode_profile(id))
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
        
# Playback/realtime start/stop - check every 200mSecs
async def black_button_task():
    while True:
        black_button.update()
        await asyncio.sleep_ms(200)
        
        
# Read the device, log to disk 
async def log_data_task():
    while True:
        if yellow_logging_state.on():
            yellow_logging_state.get_file().log(the_device.read_all())
        await asyncio.sleep_ms(10)                # log every 10 ms  
            
             
async def main():
    set_global_exception()  # Debug aid
    tasks = list()
    if the_connection.connected():
        tasks.append(asyncio.create_task(server.start_server(host='0.0.0.0', port=80, debug=True, ssl=None)))
    tasks.append(asyncio.create_task(peripheral_task()))
    tasks.append(asyncio.create_task(profile_task()))
    tasks.append(asyncio.create_task(receive_task()))
    tasks.append(asyncio.create_task(yellow_button_task()))
    tasks.append(asyncio.create_task(black_button_task()))
    tasks.append(asyncio.create_task(log_data_task()))
    tasks.append(asyncio.create_task(send_my_device_task()))
    res = await asyncio.gather(*tasks)

    
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()


