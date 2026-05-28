import geopandas as gp
import rasterio
from rasterio.enums import Resampling
import numpy as np
from rasterio.transform import xy
from pyproj import Transformer
from scipy.spatial import KDTree
from csv import DictWriter

from camera import Camera
from threat_area import ThreatArea


def extract_candidate_cameras(filepath: str) -> list[Camera]:
    cameras = []
    gdf = gp.read_file(filepath, layer="Antenas")
    for point in gdf["geometry"]:
        # TODO: choose only LTE/5G/IOT antennas.
        camera = Camera(
                len(cameras),
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


def assign_threat_areas_to_cameras(cameras: list[Camera], threat_areas: list[ThreatArea]) -> None:
    PROJECTION = "EPSG:32719"
    CAMERA_RANGE = 10000
    transformer = Transformer.from_crs("EPSG:4326", PROJECTION, always_xy=True)

    camera_array = list(transformer.transform(x.longitude, x.latitude) for x in cameras)
    area_array = list(transformer.transform(x.longitude, x.latitude) for x in threat_areas)

    camera_tree = KDTree(camera_array)
    area_tree = KDTree(area_array)

    results = camera_tree.query_ball_tree(area_tree, CAMERA_RANGE)
    for camera_index, result in enumerate(results):
        camera = cameras[camera_index]
        camera.areas_covered.extend(threat_areas[x].id for x in result)


if __name__ == "__main__":
    cameras = extract_candidate_cameras("./Mapa_Antenas_Region_08.kmz")
    print(len(cameras), "cameras extracted")
    threat_areas = extract_threat_areas("./8_amenaza.tif")
    print(len(threat_areas), "threat areas extracted")

    assign_threat_areas_to_cameras(cameras, threat_areas)

    with open("data/cameras.csv", "w") as file:
        writer = DictWriter(file, ["id", "lat", "lon"])

        writer.writeheader()
        for camera in cameras:
            writer.writerow({"id": camera.id, "lat": camera.latitude, "lon": camera.longitude})

    with open("data/threat_areas.csv", "w") as file:
        writer = DictWriter(file, ["id", "threat", "lat", "lon"])

        writer.writeheader()
        for area in threat_areas:
            writer.writerow({"id": area.id, "threat": area.threat, "lat": area.latitude, "lon": area.longitude})

    with open("data/coverage.csv", "w") as file:
        writer = DictWriter(file, ["camera_id", "area_id"])

        writer.writeheader()
        for camera in cameras:
            print(f"Camera {camera.id} covering {len(camera.areas_covered)} areas")
            for area_id in camera.areas_covered:
                writer.writerow({"camera_id": camera.id, "area_id": area_id})
