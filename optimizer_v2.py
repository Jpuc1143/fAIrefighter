import json
import time
from collections import defaultdict
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB, quicksum

from camera import Camera
from threat_area import ThreatArea

OUT_DIR = Path("resultados")
OUT_DIR.mkdir(exist_ok=True)
OUT_JSON = OUT_DIR / "solucion_v3.json"


def optimize(
    camera_count: int,
    cameras: dict[int, Camera],
    threat_areas: dict[int, ThreatArea],
    *,
    num_periods: int = 12,
    num_brigades: int = 4,
    budget: float = float("inf"),
    cost_install: float = 4.0,
    cost_maintain: float = 2.0,
    time_install: int = 1,
    time_maintain: int = 1,
    tasks_per_period: int = 22,
    maintenance_delay: int = 12,
    time_limit_s: int = 600,
):
    """
    Modelo completo fAIrefighter (informe-modelacion.pdf).

    Parámetros
    ----------
    camera_count       MC  — máximo de cámaras a instalar
    cameras            dict camera_id -> Camera (id//4 = antena, direction = k)
    threat_areas       dict area_id   -> ThreatArea
    num_periods        T   — períodos del horizonte de planificación (p.ej. 12 = 1 año mensual)
    num_brigades       J   — número de brigadas disponibles
    budget             PRE — presupuesto total en UF (inf = sin restricción)
    cost_install       CI  — costo instalación por cámara (UF, constante)
    cost_maintain      CM  — costo mantención por cámara (UF, constante)
    time_install       TI  — tareas de brigada que requiere una instalación (constante)
                            Con períodos mensuales y TI=1 día: TI=1 tarea
    time_maintain      TM  — tareas de brigada que requiere una mantención (constante)
    tasks_per_period       — tareas totales que pueden hacer TODAS las brigadas por período.
                            Con períodos mensuales y tareas de 1 día: tasks_per_period=22
                            (días hábiles/mes). Las brigadas son intercambiables, por lo
                            que se agrega su capacidad: cap_total = J * tasks_per_period.
    maintenance_delay      — períodos mínimos entre instalación y primera mantención
                            (default 12 = 1 año con períodos mensuales).
                            R7: Y[a,k,t] solo permitido si instalación completada en
                            período ≤ t - maintenance_delay.
                            R8 (mantención obligatoria) se desactiva automáticamente
                            cuando T ≤ maintenance_delay (no hay períodos factibles).
    time_limit_s           — límite de tiempo Gurobi en segundos
    """
    t0 = time.time()

    # --- Estructura de índices ---
    # Antena i = cam.id // 4,  dirección k = cam.direction
    antennas: dict[int, dict[int, Camera]] = defaultdict(dict)
    for cam in cameras.values():
        antennas[cam.id // 4][cam.direction] = cam

    ant_ids = sorted(antennas.keys())
    H = sorted(threat_areas.keys())
    T = list(range(1, num_periods + 1))
    ik_pairs = [(a, k) for a in ant_ids for k in sorted(antennas[a])]

    # HV: area_h -> [(a, k)] que la cubren
    covering: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for cam in cameras.values():
        a, k = cam.id // 4, cam.direction
        for h in cam.areas_covered:
            covering[h].append((a, k))

    # Capacidad total de brigadas por período (brigadas intercambiables → se agrega)
    cap_per_period = num_brigades * tasks_per_period
    cap_total = cap_per_period * num_periods
    maintenance_feasible = num_periods > maintenance_delay

    print(
        f"  {len(ant_ids)} antenas | {len(ik_pairs)} cámaras | "
        f"{num_brigades} brigadas | {num_periods} períodos | {len(H):,} áreas"
    )
    print(
        f"  MC={camera_count}  PRE={'∞' if budget == float('inf') else f'{budget:.1f} UF'}  "
        f"CI={cost_install} UF  CM={cost_maintain} UF  TI={time_install}  TM={time_maintain}  "
        f"tasks/período={tasks_per_period}  delay_mantención={maintenance_delay}  "
        f"cap/período={cap_per_period}  cap_total={cap_total}"
    )
    if maintenance_feasible:
        print(f"  Mantención activa: primer período posible = {maintenance_delay + time_maintain} (R7/R8 activas)")
    else:
        print(
            f"  Mantención desactivada: T={num_periods} ≤ delay={maintenance_delay} "
            f"→ R7 fuerza Y=0, R8 omitida"
        )
    if 2 * camera_count > cap_total:
        print(
            f"  ADVERTENCIA: 2×MC={2*camera_count} > cap_total={cap_total}. "
            f"Solo se podrán instalar hasta {cap_total // 2} cámaras."
        )

    print(f"[{time.time()-t0:.1f}s] Construyendo modelo Gurobi...")
    m = gp.Model("fAIrefighter_v2")
    m.Params.TimeLimit = time_limit_s
    m.Params.MIPGap = 0.01
    m.Params.OutputFlag = 1
    m.Params.Method = 3        # barrier only — evita concurrent spin (~266s desperdiciados)
    m.Params.NoRelHeurTime = 30  # 30s de heurística antes del LP → solución entera rápida

    # --- Variables ---
    # Las brigadas son intercambiables (supuesto del modelo), por lo que se agrega
    # su dimensión: X[a,k,t] representa "alguna brigada trabaja en instalar (a,k) en t".
    # La capacidad total por período se controla en R11 como J * tasks_per_period.

    # X[a,k,t]: trabajo de instalación de cámara k en antena a en período t
    X = m.addVars([(a, k, t) for (a, k) in ik_pairs for t in T], vtype=GRB.BINARY, name="X")
    # Y[a,k,t]: trabajo de mantención de cámara k en antena a en período t
    Y = m.addVars([(a, k, t) for (a, k) in ik_pairs for t in T], vtype=GRB.BINARY, name="Y")
    # Z[a,k,t]: cámara k en antena a operativa en período t
    Z = m.addVars([(a, k, t) for (a, k) in ik_pairs for t in T], vtype=GRB.BINARY, name="Z")
    # U[a,k,t]: instalación de cámara k en antena a termina en período t
    U = m.addVars([(a, k, t) for (a, k) in ik_pairs for t in T], vtype=GRB.BINARY, name="U")
    # V[a,k,t]: mantención de cámara k en antena a termina en período t
    V = m.addVars([(a, k, t) for (a, k) in ik_pairs for t in T], vtype=GRB.BINARY, name="V")
    # W[h,t]: área h cubierta en período t
    W = m.addVars([(h, t) for h in H for t in T], vtype=GRB.BINARY, name="W")

    m.update()
    print(f"[{time.time()-t0:.1f}s] Variables: {m.NumVars:,}")

    # --- Restricciones ---
    print(f"[{time.time()-t0:.1f}s] Agregando restricciones...")

    # R1: Presupuesto total
    if budget < float("inf"):
        m.addConstr(
            cost_install * quicksum(X.values()) + cost_maintain * quicksum(Y.values()) <= budget,
            name="R1_presupuesto",
        )

    # R2: Cámara operativa XOR instalándose/manteniéndose
    for a, k in ik_pairs:
        for t in T:
            m.addConstr(
                Z[a, k, t] + X[a, k, t] + Y[a, k, t] <= 1,
                name=f"R2_{a}_{k}_{t}",
            )

    # R3: Instalación termina a lo más una vez por cámara
    for a, k in ik_pairs:
        m.addConstr(quicksum(U[a, k, t] for t in T) <= 1, name=f"R3_{a}_{k}")

    # R4: Instalación terminada en t requiere TI períodos de trabajo acumulado
    for a, k in ik_pairs:
        for t in T:
            m.addConstr(
                quicksum(X[a, k, tau] for tau in range(1, t + 1)) >= time_install * U[a, k, t],
                name=f"R4_{a}_{k}_{t}",
            )

    # R5: Mantención terminada en t requiere TM períodos de trabajo acumulado
    for a, k in ik_pairs:
        for t in T:
            m.addConstr(
                quicksum(Y[a, k, tau] for tau in range(1, t + 1)) >= time_maintain * V[a, k, t],
                name=f"R5_{a}_{k}_{t}",
            )

    # R6: Cámara solo operativa si instalación terminó
    for a, k in ik_pairs:
        for t in T:
            m.addConstr(
                Z[a, k, t] <= quicksum(U[a, k, tau] for tau in range(1, t + 1)),
                name=f"R6_{a}_{k}_{t}",
            )

    # R7: Mantención solo si cámara instalada Y han pasado >= maintenance_delay períodos.
    # eligible_up_to = t - maintenance_delay: período máximo de instalación elegible.
    # Si eligible_up_to <= 0: no hay instalaciones elegibles → Y[a,k,t] = 0.
    # Si T <= maintenance_delay: todo el horizonte tiene Y=0 (ver también R8).
    for a, k in ik_pairs:
        for t in T:
            eligible_up_to = t - maintenance_delay
            if eligible_up_to <= 0:
                m.addConstr(Y[a, k, t] == 0, name=f"R7_{a}_{k}_{t}")
            else:
                m.addConstr(
                    Y[a, k, t] <= quicksum(U[a, k, tau] for tau in range(1, eligible_up_to + 1)),
                    name=f"R7_{a}_{k}_{t}",
                )

    # R8: Cada cámara instalada debe recibir al menos una mantención.
    # Solo activa si T > maintenance_delay (hay períodos factibles para mantener).
    if maintenance_feasible:
        for a, k in ik_pairs:
            m.addConstr(
                quicksum(U[a, k, t] for t in T) <= quicksum(V[a, k, t] for t in T),
                name=f"R8_{a}_{k}",
            )

    # R9: No instalar más cámaras que las disponibles (en cualquier período t)
    for t in T:
        m.addConstr(
            quicksum(U[a, k, tau] for (a, k) in ik_pairs for tau in range(1, t + 1))
            <= camera_count,
            name=f"R9_{t}",
        )

    # R10: Hectárea cubierta solo si hay cámara operativa que la observe
    print(f"[{time.time()-t0:.1f}s] Agregando R10 (cobertura)...")
    for h in H:
        cover = covering[h]
        if not cover:
            for t in T:
                m.addConstr(W[h, t] == 0)
            continue
        for t in T:
            m.addConstr(W[h, t] <= quicksum(Z[a, k, t] for (a, k) in cover))

    # R11: Capacidad total de brigadas por período.
    # Brigadas intercambiables → se agrega su capacidad: cap_per_period = J * tasks_per_period.
    for t in T:
        m.addConstr(
            quicksum(X[a, k, t] for (a, k) in ik_pairs)
            + quicksum(Y[a, k, t] for (a, k) in ik_pairs)
            <= cap_per_period,
            name=f"R11_{t}",
        )

    # R12: Cada antena tiene a lo más 4 cámaras instaladas
    for a in ant_ids:
        m.addConstr(
            quicksum(U[a, k, t] for k in sorted(antennas[a]) for t in T) <= 4,
            name=f"R12_{a}",
        )

    # --- Objetivo ---
    print(f"[{time.time()-t0:.1f}s] Definiendo objetivo...")
    m.setObjective(
        quicksum(threat_areas[h].threat * W[h, t] for h in H for t in T),
        GRB.MAXIMIZE,
    )

    print(f"[{time.time()-t0:.1f}s] Resolviendo...")
    m.optimize()

    solve_time = time.time() - t0
    print(f"\n[{solve_time:.1f}s] Status: {m.Status} ({GRB.OPTIMAL=} es óptimo)")

    if m.Status not in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
        print(f"  No se encontró solución factible. Status={m.Status}")
        return

    obj_val = m.ObjVal
    gap = m.MIPGap if m.Status != GRB.OPTIMAL else 0.0

    selected = [
        (a, k, next((t for t in T if U[a, k, t].X > 0.5), None))
        for (a, k) in ik_pairs
        if sum(U[a, k, t].X for t in T) > 0.5
    ]
    covered_areas = {h for h in H if any(W[h, t].X > 0.5 for t in T)}
    ha_cubiertas = (ThreatArea.AREA_LENGTH / 100) ** 2 * len(covered_areas)

    result = {
        "MC": camera_count,
        "T": num_periods,
        "J": num_brigades,
        "PRE": budget if budget < float("inf") else None,
        "CI": cost_install,
        "CM": cost_maintain,
        "TI": time_install,
        "TM": time_maintain,
        "tasks_per_period": tasks_per_period,
        "maintenance_delay": maintenance_delay,
        "obj_val": float(obj_val),
        "gap": float(gap),
        "solve_time_s": float(solve_time),
        "status": int(m.Status),
        "camaras_instaladas": [
            {
                "antenna_id": a,
                "direction": k,
                "lat": antennas[a][k].latitude,
                "lon": antennas[a][k].longitude,
                "periodo_instalacion": t_inst,
                "periodo_mantencion": next(
                    (t for t in T if V[a, k, t].X > 0.5), None
                ),
            }
            for (a, k, t_inst) in selected
        ],
        "hectareas_cubiertas_total": ha_cubiertas,
        "areas_cubiertas": len(covered_areas),
    }

    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n=== Solución ===")
    print(f"  Objetivo:          {obj_val:,.0f}")
    print(f"  Gap:               {gap * 100:.2f}%")
    print(f"  Cámaras usadas:    {len(selected)} / {camera_count}")
    for a, k, t_inst in selected:
        t_maint = next((t for t in T if V[a, k, t].X > 0.5), None)
        maint_str = f"  mantención t={t_maint}" if t_maint else "  (sin mantención)"
        print(
            f"    Antena={a:>3}  Dir={k}  instalada t={t_inst:>2}{maint_str}  "
            f"({antennas[a][k].latitude:.4f}°, {antennas[a][k].longitude:.4f}°)"
        )
    print(f"\n  Hectáreas cubiertas: {ha_cubiertas:,}")
    print(f"  Áreas cubiertas:     {len(covered_areas):,}")
    print(f"\n  Guardado: {OUT_JSON}")
