import json
import folium
from folium import plugins
import geopandas as gpd
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

SOL_PATH = Path("resultados/solucion_piloto.json")
SHP_PATH = Path("amenaza/8_amenaza_shape.shp")
OUT_HTML = Path("resultados/mapa_cobertura.html")
Out_DIR = Path("resultados")
Out_DIR.mkdir(exist_ok=True)

BUFFER_M = 15_000
MAX_POLYS = 50_000  # muestra para no colapsar HTML

# Color por gridcode
GC_COLOR = {
    1: "#ffffb2",  # baja
    2: "#fecc5c",  # moderada
    3: "#fd8d3c",  # alta
    4: "#e31a1c",  # muy alta
}
GC_LABEL = {1: "Baja", 2: "Moderada", 3: "Alta", 4: "Muy alta"}

print("Cargando solución...")
with open(SOL_PATH) as f:
    sol = json.load(f)

print(f"  Objetivo: {sol['obj_val']:,.0f}  |  {len(sol['antenas_seleccionadas'])} antenas  |  {sol['hectareas_cubiertas_total']:,} ha")

print("Cargando shapefile amenaza (muestra)...")
gdf = gpd.read_file(SHP_PATH)
gdf = gdf[gdf["gridcode"] >= 1].copy()
# Muestra estratificada por gridcode
sample_parts = []
for gc in [1, 2, 3, 4]:
    sub = gdf[gdf["gridcode"] == gc]
    n = min(len(sub), MAX_POLYS // 4)
    sample_parts.append(sub.sample(n, random_state=42) if len(sub) > n else sub)
gdf_s = pd.concat(sample_parts).to_crs("EPSG:4326")
print(f"  Muestra: {len(gdf_s):,} polígonos")

# Centro del mapa: media de antenas seleccionadas
lats = [a["lat"] for a in sol["antenas_seleccionadas"]]
lons = [a["lon"] for a in sol["antenas_seleccionadas"]]
center = [sum(lats)/len(lats), sum(lons)/len(lons)]

m = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")

# Capa de amenaza por gridcode
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

# Antenas seleccionadas + círculos de cobertura
ant_layer = folium.FeatureGroup(name="Antenas seleccionadas", show=True)
cov_layer = folium.FeatureGroup(name="Cobertura 15 km", show=True)

for a in sol["antenas_seleccionadas"]:
    popup_html = f"""
    <b>Antena {a['id']}</b><br>
    Lat: {a['lat']:.4f}, Lon: {a['lon']:.4f}<br>
    UTM: ({a['easting']:.0f}, {a['northing']:.0f})
    """
    folium.Marker(
        location=[a["lat"], a["lon"]],
        popup=folium.Popup(popup_html, max_width=250),
        icon=folium.Icon(color="red", icon="star", prefix="fa"),
    ).add_to(ant_layer)

    folium.Circle(
        location=[a["lat"], a["lon"]],
        radius=BUFFER_M,
        color="#e74c3c",
        weight=2,
        fill=True,
        fill_opacity=0.08,
    ).add_to(cov_layer)

ant_layer.add_to(m)
cov_layer.add_to(m)

# Leyenda HTML
legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
padding:12px;border-radius:8px;border:1px solid #ccc;font-size:13px;">
<b>fAIrefighter — Amenaza</b><br>
"""
for gc in [1, 2, 3, 4]:
    legend_html += f'<span style="background:{GC_COLOR[gc]};padding:2px 10px;margin-right:5px;">&nbsp;</span>{GC_LABEL[gc]}<br>'
legend_html += f"<hr><b>Solución piloto</b><br>MC={sol['MC']} cámaras<br>Obj={sol['obj_val']:,.0f}<br>Ha cubiertas={sol['hectareas_cubiertas_total']:,}</div>"
m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl(collapsed=False).add_to(m)

m.save(OUT_HTML)
print(f"Guardado: {OUT_HTML}")
