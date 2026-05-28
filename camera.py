from enum import Enum


class CameraDirection(Enum):
    EAST = 0
    NORTH = 1
    WEST = 2
    SOUTH = 3


class Camera:
    VIEW_ANGLE = 120
    VIEW_RANGE = 10000

    id: int
    direction: CameraDirection
    latitude: float
    longitude: float
    areas_covered: list[int]

    def __init__(self, id, direction, *, lat, lon):
        self.id = id
        self.direction = direction
        self.latitude = lat
        self.longitude = lon
        self.areas_covered = []
