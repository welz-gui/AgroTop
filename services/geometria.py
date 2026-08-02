"""Cálculo de área, perímetro e centroide para polígonos de piquete (funções puras).

DOCUMENTAÇÃO DE PROJEÇÃO CARTOGRÁFICA E ERRO EVITADO:
Coordenadas de GPS vêm em graus geográficos (EPSG:4326 - WGS 84).
Medir áreas diretamente em graus (deg²) resulta em valores sem significado físico.
Além disso, a conversão ingênua multiplicando graus por um fator fixo (1° ≈ 111,32 km)
ignora que o grau de longitude encolhe conforme a latitude se afasta do Equador. Em Mato Grosso
(lat ≈ -13.3°), essa aproximação ingênua causa um erro relativo de ~4.3% na medição de área.

Para evitar distorções cartográficas, o módulo identifica automaticamente a Zona UTM correspondente
ao centroide do polígono (para a região central de MT, Zona 21S - EPSG:32721 / EPSG:31981) e projeta
as coordenadas para metros planos antes de calcular área (em hectares) e perímetro (em metros).
"""

import math
import pyproj
from shapely.geometry import Polygon
from shapely.ops import transform


def _normalizar_anel(anel: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Fecha o anel se o último ponto não for igual ao primeiro."""
    if not anel:
        return []
    coords = list(anel)
    if len(coords) > 1 and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def _obter_poligono_projetado(poly: Polygon) -> Polygon:
    """Projeta um polígono WGS84 (EPSG:4326) para a Zona UTM correspondente ao seu centroide."""
    cx, cy = poly.centroid.x, poly.centroid.y
    zone = int((cx + 180) / 6) + 1
    epsg = (32700 if cy < 0 else 32600) + zone
    projector = pyproj.Transformer.from_crs(
        "EPSG:4326", f"EPSG:{epsg}", always_xy=True
    ).transform
    return transform(projector, poly)


def validar(anel: list[tuple[float, float]]) -> list[str]:
    """Problemas que impedem o uso do polígono. Lista vazia = válido.

    Detecta: menos de 3 vértices, coordenada fora de faixa (lon -180..180, lat -90..90),
    polígono auto-interceptante/inválido e área zero.
    """
    erros: list[str] = []
    if not isinstance(anel, (list, tuple)):
        return ["Entrada deve ser uma lista de coordenadas (lon, lat)."]

    # Remover ponto de fechamento para contar vértices únicos
    coords_unicas = list(anel)
    if len(coords_unicas) > 1 and coords_unicas[0] == coords_unicas[-1]:
        coords_unicas.pop()

    if len(coords_unicas) < 3:
        erros.append("Polígono deve ter pelo menos 3 vértices.")

    for pt in anel:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            erros.append("Cada vértice deve conter (longitude, latitude).")
            break
        lon, lat = pt[0], pt[1]
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            erros.append("Coordenadas devem ser numéricas.")
            break
        if math.isnan(lon) or math.isnan(lat):
            erros.append("Coordenadas não podem conter valores NaN.")
            break
        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            erros.append(
                f"Coordenada fora da faixa válida (lon -180..180, lat -90..90): ({lon}, {lat})."
            )

    if erros:
        return erros

    anel_fechado = _normalizar_anel(anel)
    try:
        poly = Polygon(anel_fechado)
        if not poly.is_valid or not poly.is_simple:
            erros.append("Polígono auto-interceptante ou geometria inválida.")
        elif poly.area == 0:
            erros.append("Polígono possui área zero.")
    except Exception as exc:
        erros.append(f"Erro na geometria do polígono: {exc}")

    return erros


def area_hectares(anel: list[tuple[float, float]]) -> float:
    """Área do polígono em hectares.

    `anel`: vértices [(lon, lat), ...] em graus (EPSG:4326), em ordem.
    Fecha o anel sozinho se o último ponto não repetir o primeiro.
    """
    erros = validar(anel)
    if erros:
        raise ValueError(f"Polígono inválido para cálculo de área: {erros[0]}")

    anel_fechado = _normalizar_anel(anel)
    poly = Polygon(anel_fechado)
    poly_proj = _obter_poligono_projetado(poly)
    return float(poly_proj.area / 10000.0)


def centroide(anel: list[tuple[float, float]]) -> tuple[float, float]:
    """Centroide em (lon, lat) — serve à previsão do tempo por piquete."""
    erros = validar(anel)
    if erros:
        raise ValueError(f"Polígono inválido para cálculo de centroide: {erros[0]}")

    anel_fechado = _normalizar_anel(anel)
    poly = Polygon(anel_fechado)
    c = poly.centroid
    return (float(c.x), float(c.y))


def perimetro_metros(anel: list[tuple[float, float]]) -> float:
    """Perímetro do polígono em metros."""
    erros = validar(anel)
    if erros:
        raise ValueError(f"Polígono inválido para cálculo de perímetro: {erros[0]}")

    anel_fechado = _normalizar_anel(anel)
    poly = Polygon(anel_fechado)
    poly_proj = _obter_poligono_projetado(poly)
    return float(poly_proj.length)
