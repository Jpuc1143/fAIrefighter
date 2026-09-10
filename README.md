# fAIrefighter

Modelo de optimizacion (MIP) para el despliegue de camaras de deteccion temprana de
incendios forestales sobre sitios de antena existentes en la Region del Biobio.

## Datos

Este repositorio **no contiene datos de infraestructura real**. Los archivos de entrada
con coordenadas de sitios estan excluidos por `.gitignore` y deben obtenerse por los
canales internos correspondientes.

| Archivo esperado | Contenido | Estado |
|---|---|---|
| `data/cameras.csv` | `id,direction,lat,lon` de sitios candidatos | No versionado |
| `data/coverage.csv` | `camera_id,area_id` | No versionado |
| `data/threat_areas.csv` | `id,threat,lat,lon` | No versionado |
| `Mapa_Antenas_Region_08.kmz` | Fuente GIS de sitios | No versionado |
| `8_amenaza.tif` | Raster de amenaza de incendio | No versionado |

Para ejecutar sin datos reales, existen equivalentes sinteticos con la misma estructura:

```
data/cameras.sample.csv
data/coverage.sample.csv
data/threat_areas.sample.csv
```

Las coordenadas de los `.sample.csv` son pseudoaleatorias dentro del bounding box de la
region y no corresponden a ningun sitio real. Se regeneran con `scripts/gen_sample.py`.

## Reglas de manejo de datos

1. No commitear `data/*.csv`, `*.kmz`, `*.tif`, `*.pdf` ni `output-log*.txt`.
2. Los logs de ejecucion imprimen coordenadas de sitios: mantenerlos fuera del repo.
3. Antes de cada `push`, revisar `git status` y `git log --stat`.

## Uso

```bash
uv sync
uv run python processing.py   # genera los CSV desde el KMZ y el raster
uv run python main.py         # resuelve el modelo
uv run python 05_visualize_v2.py
```

Requiere licencia de Gurobi.
