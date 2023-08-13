# Copyright @ 2023 Adrian Blakey, All rights reserved.

class Track:
    """ Track details """
    TRACK_LANES = []
    TRACK_LANES = [[] for i in range(9)]
    LANE_COLORS_4 = ['red', 'white', 'blue', 'black']
    LANE_COLORS_5 = ['red', 'blue', 'white', 'yellow', 'black']
    LANE_COLORS_6 = ['red', 'white', 'green', 'blue', 'yellow', 'black']
    LANE_COLORS_7 = ['red', 'white', 'green', 'orange', 'blue', 'yellow', 'black']
    LANE_COLORS_8 = ['red', 'white', 'green', 'orange', 'blue', 'yellow', 'purple', 'black']
    LANE_COLORS = LANE_COLORS_4  # default
    LANE_COUNT = 4  # default
    TRACK_LANES[4] = LANE_COLORS_4
    TRACK_LANES[5] = LANE_COLORS_5
    TRACK_LANES[6] = LANE_COLORS_6
    TRACK_LANES[7] = LANE_COLORS_7
    TRACK_LANES[8] = LANE_COLORS_8

    def __init__(self, number_of_lanes: int = 8, my_lane: int = 0, my_lane_color: str = ''):
        self._number_of_lanes = number_of_lanes
        self._my_lane = my_lane
        self._my_lane_color = my_lane_color

    @property
    def number_of_lanes(self) -> int:
        return self._number_of_lanes

    @number_of_lanes.setter
    def number_of_lanes(self, number_of_lanes: int):
        self._number_of_lanes = number_of_lanes

    @property
    def my_lane(self) -> int:
        return self._my_lane

    @my_lane.setter
    def my_lane(self, my_lane: int):
        self._my_lane = my_lane

    @property
    def my_lane_color(self) -> str:
        return self._my_lane_color

    @my_lane_color.setter
    def my_lane_color(self, my_lane_color: str):
        self._my_lane_color = my_lane_color

    def __str__(self) -> str:
        return str(self._number_of_lanes) + ' ' + str(self._my_lane) + ' ' + str(self._my_lane_color)
