from data import get_cameras, get_threat_areas
from optimizer_v2 import optimize


if __name__ == "__main__":
    cameras = get_cameras("./data/cameras.csv", "./data/coverage.csv")
    threat_areas = get_threat_areas("./data/threat_areas.csv")

    optimize(
        camera_count=100,
        cameras=cameras,
        threat_areas=threat_areas,
        num_periods=12,          # T: horizonte = 2 años (necesario para que delay=12 sea efectivo)
        num_brigades=4,          # J: brigadas disponibles
        budget=400,     # PRE: sin restricción de presupuesto
        cost_install=4.0,        # CI: 4 UF por cámara (informe sec. 1.2)
        cost_maintain=2.0,       # CM: 2 UF por mantención
        time_install=1,          # TI: 1 tarea de brigada (= 1 día)
        time_maintain=1,         # TM: 1 tarea de brigada (= 1 día)
        tasks_per_period=22,     # días hábiles/mes
        maintenance_delay=12,    # mantención solo a partir del mes 13 post-instalación
        time_limit_s=1800,
    )
