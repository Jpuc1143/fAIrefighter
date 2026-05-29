import geopandas as gp
import rasterio
from rasterio.enums import Resampling
import numpy as np
from rasterio.transform import xy
from pyproj import Transformer
from scipy.spatial import KDTree
from csv import DictWriter
import math

from camera import Camera, CameraDirection
from threat_area import ThreatArea


def extract_candidate_cameras(filepath: str) -> list[Camera]:
    cameras = []
    gdf = gp.read_file(filepath, layer="Antenas")
    for point in gdf["geometry"]:
        # TODO: choose only LTE/5G/IOT antennas.
        for direction in CameraDirection:
            camera = Camera(
                len(cameras),
                direction.value,
                lat=point.y,
                lon=point.x,
            )

            cameras.append(camera)

    return cameras


def extract_threat_areas(filepath: str) -> list[ThreatArea]:
    with rasterio.open(filepath) as src:
        CELL_LENGTH = 10
        scale = ThreatArea.AREA_LENGTH // CELL_LENGTH
        data = src.read(
            1,
            out_shape=(src.height // scale, src.width // scale),
            resampling=Resampling.average,
        )

        print("Finished loading threat areas data")

        transform = src.transform * src.transform.scale(scale, scale)
        valid_rows, valid_cols = np.where(data != src.nodata)
        threat_values = data[valid_rows, valid_cols]

        xs, ys = xy(transform, valid_rows, valid_cols)
        transformer = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
        lons, lats = transformer.transform(xs, ys)

        threat_areas = []
        for lat, lon, threat in zip(lats, lons, threat_values):
            area = ThreatArea(
                len(threat_areas),
                threat,
                lat=lat,
                lon=lon,
            )

            threat_areas.append(area)

        return threat_areas


def assign_threat_areas_to_cameras(
    cameras: list[Camera], threat_areas: list[ThreatArea]
) -> None:
    PROJECTION = "EPSG:32719"
    transformer = Transformer.from_crs("EPSG:4326", PROJECTION, always_xy=True)

    camera_array = list(transformer.transform(x.longitude, x.latitude) for x in cameras)
    area_array = list(
        transformer.transform(x.longitude, x.latitude) for x in threat_areas
    )

    camera_tree = KDTree(camera_array)
    area_tree = KDTree(area_array)

    results = camera_tree.query_ball_tree(area_tree, Camera.VIEW_RANGE)
    for camera_index, result in enumerate(results):
        camera = cameras[camera_index]
        for area_index in result:
            angle = np.degrees(
                math.atan2(area_array[area_index][1], area_array[area_index][0])
            )
            angle = (angle + 360) % 360
            if abs(angle - 90 * camera.direction) <= Camera.VIEW_ANGLE / 2:
                camera.areas_covered.append(threat_areas[area_index].id)


if __name__ == "__main__":
    cameras = extract_candidate_cameras("./Mapa_Antenas_Region_08.kmz")
    print(len(cameras), "cameras extracted")

    threat_areas = extract_threat_areas("./8_amenaza.tif")
    print(len(threat_areas), "threat areas extracted")

    assign_threat_areas_to_cameras(cameras, threat_areas)

    with open("data/cameras.csv", "w") as file:
        writer = DictWriter(file, ["id", "direction", "lat", "lon"])

        writer.writeheader()
        for camera in cameras:
            writer.writerow(
                {
                    "id": camera.id,
                    "direction": camera.direction,
                    "lat": camera.latitude,
                    "lon": camera.longitude,
                }
            )

    with open("data/threat_areas.csv", "w") as file:
        writer = DictWriter(file, ["id", "threat", "lat", "lon"])

        writer.writeheader()
        for area in threat_areas:
            writer.writerow(
                {
                    "id": area.id,
                    "threat": area.threat,
                    "lat": area.latitude,
                    "lon": area.longitude,
                }
            )

    with open("data/coverage.csv", "w") as file:
        writer = DictWriter(file, ["camera_id", "area_id"])

        writer.writeheader()
        for camera in cameras:
            for area_id in camera.areas_covered:
                writer.writerow({"camera_id": camera.id, "area_id": area_id})
