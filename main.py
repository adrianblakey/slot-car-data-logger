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

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("main")
log.info('Starting main')

from context import Context, the_context
from config import Config

the_config = Config()
the_config.read_profiles()
log.debug('The config object %s', the_config)

the_context.put('config', the_config) # TODO implement this

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

ip_address: str = ''
the_connection: Connection = Connection()
if the_connection.connected():
    ip_address = the_connection.ip()
    log.debug('Import a webserver')
    from webserver import server, the_ls
    the_ls.set_state(black_logging_state)
else:
    log.debug('No network - no webserver')

# BT Slave/Server/Peripheral
# Device service uuids std.
_DEVICE_SVC_UUID = bluetooth.UUID(0x180A)
_DEVICE_MFG_NAME_STR = bluetooth.UUID(0x2A29)
_DEVICE_SER_NUM_STR = bluetooth.UUID(0x2A25)
_DEVICE_FW_REV_STR = bluetooth.UUID(0x2A26)
_DEVICE_SW_REV_STR = bluetooth.UUID(0x2A28)
# Device information service
device_information_service = aioble.Service(_DEVICE_SVC_UUID) 
# Device characteristics
device_send_mfg = aioble.Characteristic(device_information_service, _DEVICE_MFG_NAME_STR, read=True, initial="Adrian's And Richard's Technologies (AART)")
device_send_ser = aioble.Characteristic(device_information_service, _DEVICE_SER_NUM_STR, read=True, initial=the_config.my_id())
device_send_fw = aioble.Characteristic(device_information_service, _DEVICE_FW_REV_STR, read=True, initial=ip_address + ' ' + sys.version)
device_send_sw = aioble.Characteristic(device_information_service, _DEVICE_SW_REV_STR, read=True, initial='Slot Car Logger; V1.0alpha')

# Profile service uuids
_PROFILE_SVC_UUID = bluetooth.UUID('ed0dfe6c-6957-4a59-9a9a-2c527cfe5a49')   # Custom profile service vendor-specific UUID
_PROFILE_ID_STR = bluetooth.UUID('ed0dfe6d-6957-4a59-9a9a-2c527cfe5a49')     # Send/recv data
_PROFILE_ERR_STR = bluetooth.UUID('ed0dfe6e-6957-4a59-9a9a-2c527cfe5a49')
_PROFILE_ERR_DESC = bluetooth.UUID(0x2904)
# Profile service
profile_service = aioble.Service(_PROFILE_SVC_UUID)           
# Read current profile value from store
global profile
init_val = ''
try:
    profile = the_config.get_profile()
    id_str = str(profile.id())
    init_val = "Id: " + id_str + " Tr: " + profile.track() + " Ln: " + profile.lane()
except ValueError as ex:
    pass
# Profile characteristics
profile_id_char = aioble.Characteristic(profile_service, _PROFILE_ID_STR, write=True, read=True, notify=True, indicate=True, capture=True, initial=id_str)
profile_err_char = aioble.Characteristic(profile_service, _PROFILE_ERR_STR, read=True, notify=True, initial=init_val)
profile_err_desc = aioble.Descriptor(profile_err_char, _PROFILE_ERR_DESC, read=True)
#profile_err_desc.write(0b00000110_00000000_0010011100100110_00000000_0000000000000000)

# Logger service uuids
_LOGGER_SVC_UUID = bluetooth.UUID('B1190EFA-176F-4B32-A715-89B3425A4076') 
_LOGGER_TUPLE = bluetooth.UUID('B1190EFB-176F-4B32-A715-89B3425A4076')
# Logger service
logger_service = aioble.Service(_LOGGER_SVC_UUID)  
logger_tuple_char = aioble.Characteristic(logger_service, _LOGGER_TUPLE, read=True, notify=True)

_ADV_APPEARANCE_LOGGER = const(128) # generic computer org.bluetooth.characteristic.gap.appearance.xml 
_ADV_INTERVAL_MS = 250_000  # 259k

aioble.register_services(device_information_service, profile_service, logger_service)

bt_connection: DeviceConnection = None  # global - the bt connection

# Serially wait for connections. Don't advertise while a central is
# connected - single connection.
# TODO what if we want 2 connections - one to stream to a server - another to phone say?
# TODO If we are happy with one connection - stop advertising!
async def peripheral_task():
    global bt_connection
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="Lgr_" + the_config.my_id()[0:6], 
            services=[ _DEVICE_SVC_UUID, _PROFILE_SVC_UUID, _LOGGER_SVC_UUID],
            appearance=_ADV_APPEARANCE_LOGGER
        ) as bt_connection:
            log.debug('Made connection %s', bt_connection)
            while bt_connection.is_connected() == True:
                await asyncio.sleep_ms(5000)

async def send_logger_task():
    while True:
        if bt_connection and bt_connection.is_connected():
            try:
                #rec = the_device.read()
                #log.debug('record %s', rec)
                logger_tuple_char.notify(bt_connection, struct.pack("<35s", the_device.read()))
            except OSError as ex:
                log.info('Connection lost')
        await asyncio.sleep_ms(1000)

async def profile_task():
    # Changes the profile by an id from the bt client
    while True:
        connection, data = await profile_id_char.written()
        log.debug("Received connection from %s", connection.device)
        profile_id_int = int.from_bytes(data, 'little')
        profile_id_str = data.decode()
        if profile_id_int > int(profile_id_str):
            profile_id_int = int(profile_id_str)
        #unp = struct.unpack("<h", data)
        log.debug("Received data %s", str(profile_id_int))
        try:
            profile = the_config.get_profile() # throws
            id: int = profile.id() 
            the_config.use_id(profile_id_int)
            id = profile_id_int # no excp - overwrite
            profile_id_char.write(struct.pack("<h", int(id)))
            profile_err_char.write(struct.pack("<50s", "Id: " + str(profile_id_int) +
                                               " Tr: " + profile.track() +
                                               " Ln: " + profile.lane() ))
        except ValueError as ex:
            log.debug('Not a profile id %s', ex)
            profile_err_char.write(struct.pack("<30s", "Unusable id. " + str(profile_id_int)))
        profile_id_char.write(struct.pack("<h", int(id))) # write a good val back
        profile_id_char.notify(connection)
        profile_err_char.notify(connection)
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
    tasks.append(asyncio.create_task(send_logger_task()))
    tasks.append(asyncio.create_task(yellow_button_task()))
    tasks.append(asyncio.create_task(black_button_task()))
    tasks.append(asyncio.create_task(log_data_task()))
    from buzzer import Buzzer, the_buzzer  # Play at last moment before execution
    res = await asyncio.gather(*tasks)
   
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
