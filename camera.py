class Camera:
    id: int
    latitude: float
    longitude: float
    areas_covered: list[int]

    def __init__(self, id, *, lat, lon):
        self.id = id
        self.latitude = lat
        self.longitude = lon
        self.areas_covered = []
