"""Genera datasets sinteticos con la misma estructura que los reales.

Coordenadas generadas con una grilla pseudoaleatoria acotada al bounding box
de la Region del Biobio. No corresponden a sitios reales de ninguna red.
"""
import random
from csv import DictWriter

random.seed(1113)

N_SITES = 40
LAT_MIN, LAT_MAX = -38.5, -36.4
LON_MIN, LON_MAX = -73.2, -71.2
AREA_STEP = 0.05

sites = [
    (round(random.uniform(LAT_MIN, LAT_MAX), 6), round(random.uniform(LON_MIN, LON_MAX), 6))
    for _ in range(N_SITES)
]

with open("data/cameras.sample.csv", "w", newline="") as f:
    w = DictWriter(f, ["id", "direction", "lat", "lon"])
    w.writeheader()
    cam_id = 0
    cameras = []
    for lat, lon in sites:
        for direction in range(4):
            w.writerow({"id": cam_id, "direction": direction, "lat": lat, "lon": lon})
            cameras.append((cam_id, direction, lat, lon))
            cam_id += 1

areas = []
area_id = 0
lat = LAT_MIN
while lat < LAT_MAX:
    lon = LON_MIN
    while lon < LON_MAX:
        areas.append((area_id, random.randint(1, 5), round(lat, 6), round(lon, 6)))
        area_id += 1
        lon += AREA_STEP
    lat += AREA_STEP

with open("data/threat_areas.sample.csv", "w", newline="") as f:
    w = DictWriter(f, ["id", "threat", "lat", "lon"])
    w.writeheader()
    for aid, threat, alat, alon in areas:
        w.writerow({"id": aid, "threat": threat, "lat": alat, "lon": alon})

# Cobertura: aproximacion por caja de 0.15 grados y cuadrante segun direccion.
RADIUS = 0.15
with open("data/coverage.sample.csv", "w", newline="") as f:
    w = DictWriter(f, ["camera_id", "area_id"])
    w.writeheader()
    for cam_id, direction, clat, clon in cameras:
        for aid, _, alat, alon in areas:
            dlat, dlon = alat - clat, alon - clon
            if abs(dlat) > RADIUS or abs(dlon) > RADIUS:
                continue
            quadrant = {0: dlon > 0, 1: dlat > 0, 2: dlon < 0, 3: dlat < 0}[direction]
            if quadrant:
                w.writerow({"camera_id": cam_id, "area_id": aid})

print("sample datasets generados")
