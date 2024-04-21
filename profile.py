# Copyright @ 2023, Adrian Blakey. All rights reserved
# A profile - simple description of what we are running - track+ lane
# TODO - add controller, controller settings, car, motor, esc ...

class Profile():
    
    def __init__(self, track: str, lane:  str, id: int):
        self._track: str = track
        self._lane: str = lane
        self._id: int = id
        
    def id(self) -> int:
        return self._id
    
    def track(self) -> str:
        return self._track
    
    def lane(self) -> str:
        return self._lane