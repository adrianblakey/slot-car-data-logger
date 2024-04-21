# Copyright @ 2023, Adrian Blakey. All rights reserved
# A bluetooth charcteristic
# Not used

import aioble

class Bt_Characteristic():
    
    def __init__(self, uuid: str, ):
        self._service = aioble.Service(uuid)
        
        
        
if __name__ == "__main__":
    aioble.Characteristic(logger_service, _LOGGER_PROFILE_SEND_UUID, read=True, notify=True)