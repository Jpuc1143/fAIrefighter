class ThreatArea:
    AREA_LENGTH = 1000 # meters -> 10 ha x 10 ha

    id: int
    threat: int
    latitude: float
    longitude: float

    def __init__(self, id, threat, *, lat: float, lon: float):
        self.id = id
        self.threat = threat
        self.latitude = lat
        self.longitude = lon
