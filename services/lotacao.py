"""Serviço de cálculo de lotação e verificação de sobreposição de piquetes.

Projeta todos os polígonos em um único sistema de coordenadas UTM (o do centro
do primeiro polígono válido) para evitar falsas sobreposições entre piquetes
em zonas UTM diferentes.
"""

import math
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.ops import transform

from services.constantes import UA_WEIGHT
from services.geometria import validar


def _obter_utm_crs(lon: float, lat: float) -> CRS:
    zona = min(60, max(1, math.floor((lon + 180.0) / 6.0) + 1))
    return CRS.from_dict({
        "proj": "utm",
        "zone": zona,
        "south": lat < 0.0,
        "datum": "WGS84",
        "units": "m",
    })


def _projetar_poligono_no_crs(
    anel: list[tuple[float, float]], crs_utm: CRS
) -> Polygon:
    coordenadas = [(float(lon), float(lat)) for lon, lat in anel]
    if len(coordenadas) > 1 and coordenadas[0] == coordenadas[-1]:
        coordenadas.pop()
    poligono = Polygon(coordenadas)
    para_utm = Transformer.from_crs("EPSG:4326", crs_utm, always_xy=True)
    return transform(para_utm.transform, poligono)


def lotacao(area_ha: float, animais: list[dict[str, Any]]) -> dict[str, Any]:
    """Lotação atual do piquete.

    `animais`: [{"id": str, "peso": float}, ...]
    Uma UA = 450 kg de peso vivo (`services.constantes.UA_WEIGHT`).

    Retorna {
      "ua_total": float, "ua_por_ha": float,
      "cabecas": int, "peso_total": float,
    }
    """
    if not animais:
        return {
            "ua_total": 0.0,
            "ua_por_ha": 0.0,
            "cabecas": 0,
            "peso_total": 0.0,
        }

    cabecas = len(animais)
    peso_total = sum(float(a.get("peso", 0.0)) for a in animais)
    ua_total = peso_total / UA_WEIGHT

    if area_ha <= 0.0:
        ua_por_ha = 0.0
    else:
        ua_por_ha = ua_total / area_ha

    return {
        "ua_total": round(ua_total, 4),
        "ua_por_ha": round(ua_por_ha, 4),
        "cabecas": cabecas,
        "peso_total": round(peso_total, 2),
    }


def capacidade(area_ha: float, ua_por_ha_alvo: float) -> dict[str, Any]:
    """Quantas UA e cabeças o piquete comporta na lotação alvo.

    Retorna {"ua_suportadas": float, "cabecas_450kg": int}
    """
    if area_ha <= 0.0 or ua_por_ha_alvo <= 0.0:
        return {
            "ua_suportadas": 0.0,
            "cabecas_450kg": 0,
        }

    ua_suportadas = area_ha * ua_por_ha_alvo
    cabecas_450kg = int(ua_suportadas)

    return {
        "ua_suportadas": round(ua_suportadas, 4),
        "cabecas_450kg": cabecas_450kg,
    }


def avaliar_lotacao(
    area_ha: float, animais: list[dict[str, Any]], ua_por_ha_alvo: float
) -> dict[str, Any]:
    """Compara atual com alvo.

    Retorna {..., "situacao": "ocioso"|"adequado"|"sobrecarregado",
             "folga_ua": float, "mensagem": str}
    """
    res_lotacao = lotacao(area_ha, animais)
    res_capacidade = capacidade(area_ha, ua_por_ha_alvo)

    ua_por_ha = res_lotacao["ua_por_ha"]
    ua_suportadas = res_capacidade["ua_suportadas"]
    ua_total = res_lotacao["ua_total"]

    folga_ua = ua_suportadas - ua_total

    if ua_por_ha_alvo <= 0.0:
        if ua_total == 0.0:
            situacao = "adequado"
            mensagem = "Lotação adequada para meta nula."
        else:
            situacao = "sobrecarregado"
            mensagem = f"Piquete sobrecarregado: {ua_total:.2f} UA sem capacidade alvo definida."
    else:
        limite_inferior = ua_por_ha_alvo * 0.90
        limite_superior = ua_por_ha_alvo * 1.10

        if ua_por_ha < limite_inferior:
            situacao = "ocioso"
            mensagem = f"Piquete ocioso: {ua_por_ha:.2f} UA/ha contra meta de {ua_por_ha_alvo:.2f} UA/ha."
        elif ua_por_ha > limite_superior:
            situacao = "sobrecarregado"
            mensagem = f"Piquete sobrecarregado: {ua_por_ha:.2f} UA/ha contra meta de {ua_por_ha_alvo:.2f} UA/ha."
        else:
            situacao = "adequado"
            mensagem = f"Lotação adequada: {ua_por_ha:.2f} UA/ha (meta {ua_por_ha_alvo:.2f} UA/ha)."

    resultado = dict(res_lotacao)
    resultado.update(res_capacidade)
    resultado.update({
        "situacao": situacao,
        "folga_ua": round(folga_ua, 4),
        "mensagem": mensagem,
    })

    return resultado


def sobrepostos(piquetes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pares de piquetes cujos polígonos se cruzam.

    Projeta todos os piquetes válidos em uma única zona UTM (a do primeiro
    piquete válido) para evitar falsas sobreposições decorrentes de origens
    UTM distintas. Sobreposições menores que 1% da área do menor piquete
    são ignoradas para evitar falso alarme por bordas que encostam.

    `piquetes`: [{"id": str, "anel": [(lon, lat), ...]}, ...]

    Retorna [{"a": str, "b": str, "area_sobreposta_ha": float,
              "pct_do_menor": float}, ...], do maior ao menor.
    """
    if not piquetes or len(piquetes) < 2:
        return []

    # Validar e coletar piquetes válidos
    validos: list[dict[str, Any]] = []
    for p in piquetes:
        anel = p.get("anel", [])
        if validar(anel):
            continue

        coordenadas = [(float(lon), float(lat)) for lon, lat in anel]
        if len(coordenadas) > 1 and coordenadas[0] == coordenadas[-1]:
            coordenadas.pop()

        poly_temp = Polygon(coordenadas)
        c = poly_temp.centroid
        zona = min(60, max(1, math.floor((c.x + 180.0) / 6.0) + 1))

        validos.append({
            "id": str(p.get("id", "")),
            "anel": anel,
            "centro_x": c.x,
            "centro_y": c.y,
            "zona": zona,
        })

    if len(validos) < 2:
        return []

    # CRS comum baseado no primeiro piquete válido
    primeiro = validos[0]
    crs_comum = _obter_utm_crs(primeiro["centro_x"], primeiro["centro_y"])
    zona_comum = primeiro["zona"]

    # Projetar todos no CRS comum
    poligonos_projetados = []
    for item in validos:
        poly_proj = _projetar_poligono_no_crs(item["anel"], crs_comum)
        poligonos_projetados.append({
            "id": item["id"],
            "poly": poly_proj,
            "zona": item["zona"],
        })

    resultados: list[dict[str, Any]] = []
    n = len(poligonos_projetados)

    for i in range(n):
        for j in range(i + 1, n):
            p1 = poligonos_projetados[i]
            p2 = poligonos_projetados[j]

            # Se a diferença de zonas for maior que 1, estão distantes demais para comparar
            if abs(p1["zona"] - p2["zona"]) > 1:
                continue

            poly1 = p1["poly"]
            poly2 = p2["poly"]

            if not poly1.intersects(poly2):
                continue

            inter = poly1.intersection(poly2)
            area_inter_m2 = float(inter.area)
            if area_inter_m2 <= 0.0:
                continue

            area1 = float(poly1.area)
            area2 = float(poly2.area)
            menor_area = min(area1, area2)

            if menor_area <= 0.0:
                continue

            pct_do_menor = (area_inter_m2 / menor_area) * 100.0

            # Desconsiderar sobreposição < 1% do menor piquete (bordas encostando)
            if pct_do_menor < 1.0:
                continue

            area_sobreposta_ha = area_inter_m2 / 10_000.0

            resultados.append({
                "a": p1["id"],
                "b": p2["id"],
                "area_sobreposta_ha": round(area_sobreposta_ha, 4),
                "pct_do_menor": round(pct_do_menor, 2),
            })

    # Ordenar do maior ao menor por área sobreposta em hectares
    resultados.sort(key=lambda r: r["area_sobreposta_ha"], reverse=True)
    return resultados
