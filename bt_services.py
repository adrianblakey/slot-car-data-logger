# Not used - yet

_LOGGER_UUID = bluetooth.UUID('B1190EF7-176F-4B32-A715-89B3425A4076') # Custom service vendor-specific UUID
_LOGGER_PROFILE_SEND_UUID = bluetooth.UUID('B1190EF8-176F-4B32-A715-89B3425A4076')  # Transmit data
_LOGGER_PROFILE_RECV_UUID = bluetooth.UUID('B1190EF9-176F-4B32-A715-89B3425A4076')  # Receive data
_DEVICE_UUID = bluetooth.UUID(0x180A)
_DEVICE_MFG_NAME_STR = bluetooth.UUID(0x2A29)
_DEVICE_SER_NUM_STR = bluetooth.UUID(0x2A25)
_DEVICE_FW_REV_STR = bluetooth.UUID(0x2A26)
_DEVICE_SW_REV_STR = bluetooth.UUID(0x2A28)
_ADV_APPEARANCE_LOGGER = const(768)

_ADV_INTERVAL_MS = 250_000

# Register GATT server.
logger_service = aioble.Service(_LOGGER_UUID)
device_information_service = aioble.Service(_DEVICE_UUID)

profile_send_characteristic = aioble.Characteristic(logger_service, _LOGGER_PROFILE_SEND_UUID, read=True, notify=True)
profile_recv_characteristic = aioble.Characteristic(logger_service, _LOGGER_PROFILE_RECV_UUID, write=True, read=True, notify=True, capture=True, indicate=True)


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
            name="slot-car-logger",
            services=[_LOGGER_UUID, _DEVICE_UUID],
            appearance=_ADV_APPEARANCE_LOGGER,
            manufacturer=(0xabcd, b"1234"),
        ) as connection:
            log.debug("Connection from %s", connection.device)
            while connection.is_connected() == True:
                await asyncio.sleep_ms(1000)


# Helper to encode the profile id (sint16, profile index number).
def _encode_profile(id: int):
    log.debug("Encode profile %s", id)
    return struct.pack("<h", int(id))


device_sent: bool = False
async def send_my_device_task():
    # Send my device characteristic
    while True:
        if device_sent:
            break
        device_send_mfg.write(struct.pack("<4s", 'AART'))
        device_send_ser.write(struct.pack("<30s", the_config.my_id()))
        device_send_fw.write(struct.pack("<40s", sys.version))
        device_send_sw.write(struct.pack("<30s", 'Slot Car Logger; V1.0alpha'))
        device_sent = True
        await asyncio.sleep_ms(10000)


# Periodically poll the bt profile config and send it
async def profile_task():
    while True:
        profile_send_characteristic.write(_encode_profile(the_config.get_profile().id()))
        #device_send_mfg.write(struct.pack("<4s", 'AART'))
        #device_send_ser.write(struct.pack("<30s", the_config.my_id()))
        #device_send_fw.write(struct.pack("<40s", sys.version))
        #device_send_sw.write(struct.pack("<30s", 'Slot Car Logger; V1.0alpha'))
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


