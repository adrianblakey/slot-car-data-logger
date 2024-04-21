# Copyright @ 2023, Adrian Blakey. All rights reserved
# A bluetooth service - not used

from aioble import Service
from bluetooth import UUID
import logging

log = logging.getLogger("bt_service")

class Bt_Service():
    
    def __init__(self, uuid: int | str):
        self._service: Service = Service(UUID(uuid))



if __name__ == "__main__":
    try:
        the_service
    except NameError:
        log.info('the_service not yet defined')
        the_service = Bt_Service(0x180A)
        log.debug(the_service)
