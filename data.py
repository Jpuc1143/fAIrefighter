from csv import DictReader
from camera import Camera
from threat_area import ThreatArea


def get_cameras(cameras_path: str, coverage_path: str) -> list[Camera]:
    cameras: dict[int, Camera] = dict()
    with open(cameras_path, "r") as camera_file:
        camera_reader = DictReader(camera_file)
        for row in camera_reader:
            camera = Camera(
                int(row["id"]),
                int(row["direction"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
            )

            cameras[camera.id] = camera

    with open(coverage_path, "r") as coverage_file:
        coverage_reader = DictReader(coverage_file)
        for row in coverage_reader:
            camera_id = int(row["camera_id"])
            area_id = int(row["area_id"])
            cameras[camera_id].areas_covered.append(area_id)

    return cameras


def get_threat_areas(areas_path: str) -> list[ThreatArea]:
    threat_areas: dict[int, ThreatArea] = dict()
    with open(areas_path, "r") as area_file:
        area_file = DictReader(area_file)
        for row in area_file:
            area = ThreatArea(
                int(row["id"]),
                int(row["threat"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
            )

            threat_areas[area.id] = area

    return threat_areas
