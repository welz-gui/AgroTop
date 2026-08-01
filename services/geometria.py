"""Cálculos métricos para polígonos recebidos em GPS (EPSG:4326).

O módulo escolhe a zona UTM WGS84 a partir do centroide do piquete e projeta o
polígono antes de medir. Isso evita tratar graus quadrados como área e evita o
erro de supor que um grau de longitude tem o mesmo comprimento em toda latitude.
Para polígonos do tamanho de um piquete, a distorção dentro da zona UTM é pequena.
"""

import math

from pyproj import CRS, Transformer
from shapely.geometry import LinearRing, Polygon
from shapely.ops import transform


def _coordenadas(anel: list[tuple[float, float]]) -> list[tuple[float, float]]:
    coordenadas = [(float(lon), float(lat)) for lon, lat in anel]
    if len(coordenadas) > 1 and coordenadas[0] == coordenadas[-1]:
        coordenadas.pop()
    return coordenadas


def _crs_utm(lon: float, lat: float) -> CRS:
    zona = min(60, max(1, math.floor((lon + 180.0) / 6.0) + 1))
    return CRS.from_dict({
        "proj": "utm",
        "zone": zona,
        "south": lat < 0.0,
        "datum": "WGS84",
        "units": "m",
    })


def _poligono_projetado(
    anel: list[tuple[float, float]],
) -> tuple[Polygon, CRS]:
    problemas = validar(anel)
    if problemas:
        raise ValueError(" ".join(problemas))

    poligono = Polygon(_coordenadas(anel))
    centro = poligono.centroid
    crs_utm = _crs_utm(centro.x, centro.y)
    para_utm = Transformer.from_crs("EPSG:4326", crs_utm, always_xy=True)
    return transform(para_utm.transform, poligono), crs_utm


def area_hectares(anel: list[tuple[float, float]]) -> float:
    """Área do polígono em hectares.

    `anel`: vértices [(lon, lat), ...] em graus (EPSG:4326), em ordem.
    Fecha o anel sozinho se o último ponto não repetir o primeiro.
    """
    poligono, _ = _poligono_projetado(anel)
    return float(poligono.area / 10_000.0)


def centroide(anel: list[tuple[float, float]]) -> tuple[float, float]:
    """Centroide em (lon, lat) — serve à previsão do tempo por piquete."""
    poligono, crs_utm = _poligono_projetado(anel)
    centro_metrico = poligono.centroid
    para_gps = Transformer.from_crs(crs_utm, "EPSG:4326", always_xy=True)
    lon, lat = para_gps.transform(centro_metrico.x, centro_metrico.y)
    return float(lon), float(lat)


def perimetro_metros(anel: list[tuple[float, float]]) -> float:
    """Perímetro do polígono em metros."""
    poligono, _ = _poligono_projetado(anel)
    return float(poligono.length)


def validar(anel: list[tuple[float, float]]) -> list[str]:
    """Problemas que impedem o uso do polígono. Lista vazia = válido.

    Detecta menos de 3 vértices, coordenada fora da faixa EPSG:4326,
    polígono auto-interceptante e área zero.
    """
    problemas: list[str] = []

    try:
        coordenadas = _coordenadas(anel)
    except (TypeError, ValueError):
        return ["Coordenada inválida: use pares (longitude, latitude)."]

    if len(coordenadas) < 3:
        problemas.append("O polígono precisa ter pelo menos 3 vértices.")

    if any(
        not (math.isfinite(lon) and math.isfinite(lat))
        or not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0)
        for lon, lat in coordenadas
    ):
        problemas.append(
            "Coordenada fora da faixa permitida: longitude -180..180 e latitude -90..90."
        )

    if len(coordenadas) < 3:
        return problemas

    anel_geometrico = LinearRing(coordenadas)
    poligono = Polygon(coordenadas)
    if not anel_geometrico.is_simple:
        problemas.append("Polígono auto-interceptante.")
    if poligono.area == 0.0:
        problemas.append("Área do polígono é zero.")

    return problemas
