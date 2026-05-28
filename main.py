from data import get_cameras, get_threat_areas


if __name__ == "__main__":
    cameras = get_cameras("./data/cameras.csv", "./data/coverage.csv")
    threat_areas = get_threat_areas("./data/threat_areas.csv")

    # TODO optimizar

    # TODO mostrar resultados

    # TODO mostar un grafico con las antenas???"
