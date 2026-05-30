# fAIrefighter — Optimización de Despliegue de Cámaras

Modelo de optimización para el despliegue óptimo de cámaras de detección temprana de incendios forestales en la Región del Biobío, en el marco del proyecto fAIrefighter de CENIA. Maximiza la cobertura de áreas de amenaza usando torres Entel como puntos de montaje.

---

## Requisitos

- **Python 3.14+**
- **[uv](https://docs.astral.sh/uv/)** — gestor de entornos y dependencias
- **Gurobi 13+** con licencia válida (académica o comercial)

---

## Setup

### 1. Instalar uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clonar el repositorio y crear el entorno

```bash
git clone <repo-url>
cd fAIrefighter
uv sync          # crea .venv e instala todas las dependencias
```

Las dependencias se instalan automáticamente desde `pyproject.toml`:

| Paquete | Uso |
|---|---|
| `gurobipy` | Solver MIP |
| `geopandas` | Lectura de shapefiles de amenaza |
| `folium` | Visualización interactiva (HTML) |
| `rasterio` | Procesamiento raster |
| `scipy` | Utilidades científicas |

### 3. Licencia Gurobi

Gurobi requiere licencia activa. Con licencia académica:

```bash
grbgetkey <tu-clave>   # genera ~/.gurobi/gurobi.lic
```

Verifica que funciona:

```bash
uv run python -c "import gurobipy as gp; m = gp.Model(); print('Gurobi OK')"
```

---

## Datos

Los archivos de datos deben estar en `data/`. El repositorio incluye:

| Archivo | Filas | Descripción |
|---|---|---|
| `data/cameras.csv` | 2.548 | Torres Entel × 4 direcciones. Columnas: `id, direction, lat, lon` |
| `data/coverage.csv` | 322.858 | Qué áreas cubre cada cámara. Columnas: `camera_id, area_id` |
| `data/threat_areas.csv` | 24.928 | Áreas de amenaza CONAF. Columnas: `id, threat, lat, lon` |

> `threat` ∈ {1, 2, 3, 4}: baja, moderada, alta, muy alta amenaza de incendio.

### Datos opcionales (visualización)

Para correr `05_visualize.py` se necesita el shapefile de amenaza:

```
amenaza/8_amenaza_shape.shp    # ~881 MB
```

Este archivo **no está en el repositorio** por su tamaño. Si solo tienes el `.shp` (sin `.dbf`/`.shx`), el script lo reconstruye automáticamente con `SHAPE_RESTORE_SHX=YES`.

---

## Ejecutar el optimizador

```bash
uv run python main.py
```

### Parámetros en `main.py`

```python
optimize(
    camera_count=100,       # MC: máximo de cámaras a instalar (techo, no obligatorio)
    cameras=cameras,
    threat_areas=threat_areas,
    num_periods=12,         # T: horizonte en meses (12 = 1 año)
    num_brigades=4,         # J: brigadas disponibles
    budget=float("inf"),    # PRE: presupuesto en UF (inf = sin restricción)
    cost_install=4.0,       # CI: 4 UF por instalación (constante)
    cost_maintain=2.0,      # CM: 2 UF por mantención (constante)
    time_install=1,         # TI: 1 día por instalación
    time_maintain=1,        # TM: 1 día por mantención
    tasks_per_period=22,    # P: días hábiles por mes (capacidad de brigadas)
    maintenance_delay=12,   # D: meses mínimos entre instalación y mantención
    time_limit_s=1200,      # límite de tiempo Gurobi en segundos
)
```

### Escenarios comunes

| Escenario | `camera_count` | `num_periods` | `maintenance_delay` | `time_limit_s` |
|---|---|---|---|---|
| Piloto (8 cámaras) | `8` | `12` | `12` | `600` |
| Escala (100 cámaras, 1 año) | `100` | `12` | `12` | `1200`+ |
| Con mantención (2 años) | `100` | `24` | `12` | `3600`+ |

> **Nota:** Con `maintenance_delay = num_periods`, la restricción de mantención obligatoria se desactiva automáticamente (no hay períodos factibles dentro del horizonte). Esto es el escenario "Año 1": las cámaras se instalan y operan sin mantención planificada en el horizonte.

---

## Consideraciones de tiempo de cómputo

El modelo es un MIP con ~450k variables binarias (T=12). El tiempo de resolución depende fuertemente de los parámetros:

| Configuración | Variables aprox. | Tiempo típico | Gap obtenido |
|---|---|---|---|
| MC=8, T=12 | 452k | 600s | ~8.6% |
| MC=100, T=12 | 452k | 600s | ~15.6% |
| MC=100, T=12 | 452k | 1200s | ~9.6% |
| MC=100, T=24 | 900k | >1800s | — |

**Recomendaciones:**
- Para resultados de calidad (gap < 10%), usar `time_limit_s >= 1200` con MC=100.
- Duplicar T duplica las variables — evitar T=24 salvo que haya tiempo suficiente (>3600s).
- El solver usa `Method=3` (barrier) y `NoRelHeurTime=30` (30s de heurística previa): el incumbente inicial se encuentra en los primeros ~30s, el resto del tiempo mejora el gap.

---

## Archivos de salida

Los resultados se guardan en `resultados/`:

| Archivo | Descripción |
|---|---|
| `resultados/solucion_v2.json` | Solución del optimizer_v2 (parámetros + cámaras seleccionadas + cobertura) |
| `resultados/solucion_piloto.json` | Solución del optimizer original (modelo estático) |
| `resultados/mapa_cobertura.html` | Mapa interactivo Folium (generado por `05_visualize.py`) |

> El nombre del JSON de salida está fijado en `optimizer_v2.py` como `OUT_JSON`. Si corres múltiples escenarios, **renombra el archivo antes de cada corrida** para no sobreescribir resultados anteriores.

### Estructura del JSON de salida

```json
{
  "MC": 100,
  "T": 12,
  "obj_val": 376609.0,
  "gap": 0.096,
  "solve_time_s": 1206.1,
  "camaras_instaladas": [
    {
      "antenna_id": 0,
      "direction": 1,
      "lat": -38.0452,
      "lon": -71.2800,
      "periodo_instalacion": 1,
      "periodo_mantencion": null
    }
  ],
  "hectareas_cubiertas_total": 1529500.0,
  "areas_cubiertas": 15295
}
```

---

## Estructura del proyecto

```
fAIrefighter/
├── main.py              # Entry point — configura y ejecuta el optimizador
├── optimizer_v2.py      # Modelo MIP completo (T períodos, brigadas, mantención)
├── optimizer.py         # Modelo estático simplificado (sin tiempo)
├── data.py              # Carga cameras.csv y threat_areas.csv
├── camera.py            # Clase Camera (id, direction, lat, lon, areas_covered)
├── threat_area.py       # Clase ThreatArea (id, threat, lat, lon)
├── processing.py        # Utilidades de procesamiento geoespacial
├── 05_visualize.py      # Mapa interactivo de la solución (requiere shapefile)
├── data/                # CSVs de entrada
├── resultados/          # JSONs y HTML de salida
├── informe/             # Informe LaTeX (template.tex)
└── pyproject.toml       # Dependencias (uv)
```

---

## Modelo matemático

El modelo optimiza la cobertura temporal de 24.928 áreas de amenaza usando hasta `MC` cámaras instaladas en 2.548 posiciones candidatas (637 antenas × 4 direcciones). Maximiza:

$$\max \sum_{h \in H} \sum_{t \in T} W_{h,t} \cdot R_h$$

sujeto a 12 restricciones que modelan presupuesto, operatividad, secuencia instalación → operación → mantención, capacidad de brigadas y cobertura geográfica. Ver `informe/template.tex` para la formulación completa.
