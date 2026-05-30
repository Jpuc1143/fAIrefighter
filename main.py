from data import get_cameras, get_threat_areas
from optimizer import optimize


if __name__ == "__main__":
    cameras = get_cameras("./data/cameras.csv", "./data/coverage.csv")
    threat_areas = get_threat_areas("./data/threat_areas.csv")

    # TODO optimizar
    optimize(100, cameras, threat_areas)

    # TODO mostrar resultados

    # TODO mostar un grafico con las antenas???"
