"""Monta as localizações distintas usadas para buscar previsão do tempo."""


def localizacoes_para_previsao(
    propriedades: list[dict],
    farm_lat: float | None,
    farm_lon: float | None,
) -> list[dict]:
    """Agrupa propriedades pelo par de coordenadas resolvido para a previsão."""

    localizacoes: list[dict] = []
    por_coordenada: dict[tuple[float, float], dict] = {}

    for propriedade in propriedades:
        latitude = propriedade.get("latitude")
        longitude = propriedade.get("longitude")

        if latitude is None or longitude is None:
            if farm_lat is None or farm_lon is None:
                continue
            latitude, longitude = farm_lat, farm_lon

        coordenada = (latitude, longitude)
        if coordenada not in por_coordenada:
            grupo = {
                "lat": latitude,
                "lon": longitude,
                "propriedades": [],
            }
            por_coordenada[coordenada] = grupo
            localizacoes.append(grupo)

        por_coordenada[coordenada]["propriedades"].append(
            {"id": propriedade.get("id"), "nome": propriedade.get("nome")}
        )

    return localizacoes
