import json
import math
import folium
import geopandas as gpd
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

SOL_PATH = Path("resultados/solucion_v3.json")
SHP_PATH = Path("amenaza/8_amenaza_shape.shp")
OUT_HTML = Path("resultados/mapa_cobertura_v3.html")
Path("resultados").mkdir(exist_ok=True)

BUFFER_M = 15_000
FOV_DEG = 90
N_ARC = 40
MAX_POLYS = 50_000

GC_COLOR = {1: "#ffffb2", 2: "#fecc5c", 3: "#fd8d3c", 4: "#e31a1c"}
GC_LABEL = {1: "Baja", 2: "Moderada", 3: "Alta", 4: "Muy alta"}

DIR_BEARING = {0: 90, 1: 0, 2: 270, 3: 180}  # East, North, West, South
DIR_LABEL   = {0: "Este", 1: "Norte", 2: "Oeste", 3: "Sur"}
DIR_COLOR   = {0: "#3498db", 1: "#2ecc71", 2: "#9b59b6", 3: "#e67e22"}


def destination(lat, lon, bearing_deg, dist_m):
    R = 6_371_000.0
    d = dist_m / R
    lat1, lon1 = math.radians(lat), math.radians(lon)
    b = math.radians(bearing_deg)
    lat2 = math.asin(math.sin(lat1) * math.cos(d) +
                     math.cos(lat1) * math.sin(d) * math.cos(b))
    lon2 = lon1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat1),
                              math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def sector_polygon(lat, lon, radius_m, center_bearing, fov=90, n=N_ARC):
    half = fov / 2.0
    start = center_bearing - half
    step = fov / n
    pts = [[lat, lon]]
    for i in range(n + 1):
        b = start + i * step
        pts.append(list(destination(lat, lon, b, radius_m)))
    pts.append([lat, lon])
    return pts


print("Cargando solución...")
with open(SOL_PATH) as f:
    sol = json.load(f)

print(f"  Obj: {sol['obj_val']:,.0f}  |  {len(sol['antenas_seleccionadas'])} cámaras  |  {sol['hectareas_cubiertas_total']:,} ha")

print("Cargando shapefile amenaza (muestra)...")
gdf = gpd.read_file(SHP_PATH)
gdf = gdf[gdf["gridcode"] >= 1].copy()
sample_parts = []
for gc in [1, 2, 3, 4]:
    sub = gdf[gdf["gridcode"] == gc]
    n = min(len(sub), MAX_POLYS // 4)
    sample_parts.append(sub.sample(n, random_state=42) if len(sub) > n else sub)
gdf_s = pd.concat(sample_parts).to_crs("EPSG:4326")
print(f"  Muestra: {len(gdf_s):,} polígonos")

lats = [a["lat"] for a in sol["antenas_seleccionadas"]]
lons = [a["lon"] for a in sol["antenas_seleccionadas"]]
center = [sum(lats) / len(lats), sum(lons) / len(lons)]

m = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")

# Capas amenaza
for gc in [1, 2, 3, 4]:
    sub = gdf_s[gdf_s["gridcode"] == gc]
    if sub.empty:
        continue
    layer = folium.FeatureGroup(name=f"Amenaza {GC_LABEL[gc]}", show=(gc >= 3))
    for _, row in sub.iterrows():
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda f, c=GC_COLOR[gc]: {
                "fillColor": c, "color": c, "weight": 0, "fillOpacity": 0.5
            }
        ).add_to(layer)
    layer.add_to(m)

# Sectores FOV por dirección (capas separadas para toggle)
sector_layers = {}
for d, label in DIR_LABEL.items():
    sector_layers[d] = folium.FeatureGroup(name=f"FOV {label} (90°)", show=True)

ant_layer = folium.FeatureGroup(name="Antenas seleccionadas", show=True)

for a in sol["antenas_seleccionadas"]:
    d = a["direction"]
    bearing = DIR_BEARING[d]
    color = DIR_COLOR[d]

    popup_html = (
        f"<b>Antena {a['antenna_id']}</b><br>"
        f"Lat: {a['lat']:.5f}, Lon: {a['lon']:.5f}<br>"
        f"Dirección: {DIR_LABEL[d]} ({d})"
    )

    folium.Marker(
        location=[a["lat"], a["lon"]],
        popup=folium.Popup(popup_html, max_width=220),
        icon=folium.Icon(color="red", icon="camera", prefix="fa"),
    ).add_to(ant_layer)

    pts = sector_polygon(a["lat"], a["lon"], BUFFER_M, bearing)
    folium.Polygon(
        locations=pts,
        color=color,
        weight=1.5,
        fill=True,
        fill_color=color,
        fill_opacity=0.15,
        popup=folium.Popup(popup_html, max_width=220),
    ).add_to(sector_layers[d])

ant_layer.add_to(m)
for layer in sector_layers.values():
    layer.add_to(m)

# Leyenda
legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
padding:12px;border-radius:8px;border:1px solid #ccc;font-size:13px;max-width:200px;">
<b>fAIrefighter — Amenaza</b><br>
"""
for gc in [1, 2, 3, 4]:
    legend_html += (
        f'<span style="background:{GC_COLOR[gc]};padding:2px 10px;margin-right:5px;">&nbsp;</span>'
        f'{GC_LABEL[gc]}<br>'
    )
legend_html += "<hr><b>FOV cámara (90°)</b><br>"
for d, label in DIR_LABEL.items():
    legend_html += (
        f'<span style="background:{DIR_COLOR[d]};padding:2px 10px;margin-right:5px;">&nbsp;</span>'
        f'{label}<br>'
    )
legend_html += (
    f"<hr><b>Solución</b><br>MC={sol['MC']} cámaras<br>"
    f"Obj={sol['obj_val']:,.0f}<br>Ha={sol['hectareas_cubiertas_total']:,}</div>"
)
m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl(collapsed=False).add_to(m)

m.save(OUT_HTML)
print(f"Guardado: {OUT_HTML}")
