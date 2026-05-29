import json
import time
from pathlib import Path
import gurobipy as gp
from gurobipy import GRB, quicksum

from camera import Camera
from threat_area import ThreatArea

OUT_DIR = Path("resultados")
OUT_DIR.mkdir(exist_ok=True)
OUT_JSON = OUT_DIR / "solucion_piloto.json"


def optimize(
        #budget, worker_count,
        #installation_cost, maintenance_cost,
        #installation_duration, maintenance_duration,
        camera_count: int, cameras: list[Camera], threat_areas: list[ThreatArea]
        ):
    
    t0 = time.time()
    cameras = dict()
    threat_areas = dict() # TODO

    print(f"  {len(cameras) / 4} antenas, {len(threat_areas):,} áreas de amenaza")

    print(f"[{time.time()-t0:.1f}s] Construyendo modelo Gurobi...")
    m = gp.Model("fAIrefighter_piloto")
    m.Params.TimeLimit = 300
    m.Params.MIPGap = 0.01
    m.Params.OutputFlag = 1

    # Variables x[i] — install camera at antenna i
    X = m.addVars(len(cameras), vtype=GRB.BINARY, name="X")
    X = m.addVars(len(cameras), vtype=GRB.BINARY, name="X")
    X = m.addVars(len(cameras), vtype=GRB.BINARY, name="X")
    X = m.addVars(len(cameras), vtype=GRB.BINARY, name="X")
    X = m.addVars(len(cameras), vtype=GRB.BINARY, name="X")

    # Variables W[h] — hectare h covered
    W = m.addVars(len(threat_areas), vtype=GRB.BINARY, name="W")

    # Budget constraint
    m.addConstr(gp.quicksum(x for x in X) <= camera_count, name="budget")

    # Coverage constraints: W[h] <= sum of x[i] for i covering h
    print(f"[{time.time()-t0:.1f}s] Agregando restricciones de cobertura...")
    for area, w in zip(threat_areas.values(), W):
        m.addConstr(
            w <= quicksum(x if area.id in camera.areas_covered else 0 for (camera, x) in zip(cameras.values(), X)),
            name=f"cov_{area.id}"
        )

    # Objective: maximize sum Rh * W[h]
    print(f"[{time.time()-t0:.1f}s] Definiendo objetivo...")
    obj = gp.quicksum(area.threat * w for (area, w) in zip(threat_areas.values(), W))
    m.setObjective(obj, GRB.MAXIMIZE)

    print(f"[{time.time()-t0:.1f}s] Resolviendo (MC={camera_count})...")
    m.optimize()

    solve_time = time.time() - t0
    print(f"\n[{solve_time:.1f}s] Status: {m.Status} ({GRB.OPTIMAL=} es óptimo)")

    if m.Status in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
        obj_val = m.ObjVal
        gap = m.MIPGap if m.Status != GRB.OPTIMAL else 0.0

        # Selected antennas
        selected_cameras = [camera for x in zip(cameras.values(), X) if x > 0.5]

        # Covered hectares by gridcode
        covered_areas = [area for w in zip(threat_areas.values(), W) if w > 0.5]

        result = {
            "MC": camera_count,
            "obj_val": float(obj_val),
            "gap": float(gap),
            "solve_time_s": float(solve_time),
            "status": int(m.Status),
            "antenas_seleccionadas": [
                {
                    "id": camera.id,
                    "lon": camera.longitude,
                    "lat": camera.latitude,
                    "direction": camera.direction,
                }
                for camera in selected_cameras
            ],
            "hectareas_cubiertas_total": (ThreatArea.AREA_LENGTH/100)**2 * len(covered_areas),
            #"hectareas_por_gridcode": {str(k): v for k, v in sorted(gc_counts.items())},
        }

        with open(OUT_JSON, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\n=== Solución ===")
        print(f"  Objetivo: {obj_val:,.0f}")
        print(f"  Gap: {gap*100:.2f}%")
        print(f"  Cámaras usadas: {len(selected_cameras)} / {camera_count}")
        for camera in selected_cameras:
            print(f"    ID={camera.id} {camera.lat}°, {camera.lon}°")
        print(f"\n  Hectáreas cubiertas: {(ThreatArea.AREA_LENGTH/100)**2 * len(covered_areas):,}")
        print(f"  Áreas cubiertas: {len(covered_areas):,}")
        for area in covered_areas:
            print(f"    ID={area.id} R={area.threat} {area.lat}°, {area.lon}°")
        print(f"\n  Guardado: {OUT_JSON}")
    else:
        print(f"  No se encontró solución factible. Status={m.Status}")
